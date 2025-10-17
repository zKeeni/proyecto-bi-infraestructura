##lloo
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
from pyhive import hive
import logging
import os

# --- Configuración de Rutas y Conexión ---
HIVE_HOST = 'hiveserver2'
HIVE_PORT = 10000
DB_NAME = 'cacao'
HIVE_USER = 'hive'

# Rutas de los archivos (ajusta si es necesario)
PAISES_CSV_PATH = '/opt/airflow/dags/data/paises.csv'
PERIODO_CSV_PATH = '/opt/airflow/dags/data/periodo.csv'
FACT_CSV_PATH = '/opt/airflow/dags/data/exportaciones_pais_periodo.csv'
CSV_SEP = ';' # Delimitador confirmado en los CSV

# ------------------ FUNCIONES AUXILIARES ------------------ #

def leer_csv_normalizado(file_path):
    """
    Lee un CSV con delimitador de punto y coma (;) y maneja la coma (,) como decimal.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No se encuentra el archivo: {file_path}")

    try:
        # Usamos decimal=',' para que Pandas lea correctamente los números
        df = pd.read_csv(file_path, sep=CSV_SEP, decimal=',')
        df = df.fillna(0)
        return df
    except Exception as e:
        logging.error(f"Error de lectura o formato en {file_path}: {e}")
        raise

def insertar_fila_hive(cursor, table_name, row):
    """
    Inserta una fila a Hive, manejando comillas para STRINGs y convirtiendo a formato SQL.
    """
    values = []

    # Aseguramos que los valores sigan el orden de las columnas en el DataFrame
    for val in row:
        if isinstance(val, (int, float)):
            # PyHive puede manejar números directamente, y los convertiremos a DOUBLE
            values.append(str(val))
        elif isinstance(val, str):
            # Escapar comillas y encerrar en comillas para Hive STRING
            values.append(f"'{val.replace("'", "''")}'")
        else:
            values.append('NULL')

    cursor.execute(f"INSERT INTO TABLE {DB_NAME}.{table_name} VALUES ({', '.join(values)})")

# ------------------ CARGA PRINCIPAL A HIVE ------------------ #
def cargar_modelo_normalizado_hive():
    """Crea el modelo normalizado (Dimensiones + Hechos) y carga datos en Hive."""

    # 1. Leer DataFrames
    # Asegúrate que estas rutas y archivos existen y tienen el delimitador correcto (;)
    df_pais = leer_csv_normalizado(PAISES_CSV_PATH)
    df_periodo = leer_csv_normalizado(PERIODO_CSV_PATH)
    df_fact = leer_csv_normalizado(FACT_CSV_PATH) # exportaciones_pais_periodo.csv

    # 2. Conexión a HiveServer2
    conn = hive.Connection(host=HIVE_HOST, port=HIVE_PORT, username=HIVE_USER)
    cursor = conn.cursor()

    logging.info(f"Creando y usando base de datos {DB_NAME}")
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")

    # --- 3. DDL: SIN CONSTRAINTS Y CON NOMBRES COMPATIBLES ---

    # a. Dimensión País (PK/FK eliminadas del DDL)
    cursor.execute("DROP TABLE IF EXISTS dim_pais")
    cursor.execute("""
        CREATE TABLE dim_pais (
            id_pais INT,
            nombre_pais STRING
        ) STORED AS PARQUET
    """)

    # b. Dimensión Periodo
    cursor.execute("DROP TABLE IF EXISTS dim_periodo")
    cursor.execute("""
        CREATE TABLE dim_periodo (
            id_periodo INT,
            descripcion STRING
        ) STORED AS PARQUET
    """)

    # c. Tabla de Hechos (Fact) - NOMBRES CORREGIDOS (snake_case)
    # Hive no permite los nombres originales del CSV.
    cursor.execute("DROP TABLE IF EXISTS fact_exportaciones_pais")
    cursor.execute("""
        CREATE TABLE fact_exportaciones_pais (
            id_exportacion BIGINT,
            id_pais INT,
            id_periodo INT,
            peso_t_miles DOUBLE,
            fob_usd_miles DOUBLE
        ) STORED AS PARQUET
    """)

    # --- 4. Alineación y Carga de Datos ---

    # Alinear el DataFrame de Hechos con los nuevos nombres de columna de Hive
    df_fact_aligned = df_fact.copy()
    # Los nombres de tu CSV original eran: id_exportacion;id_pais;id_periodo;"Peso (t) (miles)";"FOB (USD miles)"
    df_fact_aligned.columns = ['id_exportacion', 'id_pais', 'id_periodo', 'peso_t_miles', 'fob_usd_miles']

    logging.info(f"Insertando {len(df_pais)} filas en dim_pais...")
    for _, row in df_pais.iterrows():
        insertar_fila_hive(cursor, 'dim_pais', row)

    logging.info(f"Insertando {len(df_periodo)} filas en dim_periodo...")
    for _, row in df_periodo.iterrows():
        # Usamos las primeras dos columnas del DF de período
        insertar_fila_hive(cursor, 'dim_periodo', row.iloc[:2])

    logging.info(f"Insertando {len(df_fact_aligned)} filas en fact_exportaciones_periodo...")
    for _, row in df_fact_aligned.iterrows():
        # Insertamos el DataFrame alineado
        insertar_fila_hive(cursor, 'fact_exportaciones_pais', row)


    conn.close()
    logging.info("Carga del modelo BI normalizado completada con éxito ✅")

# ------------------ DAG DE AIRFLOW ------------------ #
with DAG(
    dag_id='cargar_fact_exportaciones_paises',
    description='Crea y carga el modelo normalizado (Dimensiones y Hechos) a Hive',
    start_date=datetime(2025, 10, 5),
    catchup=False,
    schedule=None,
    tags=['bi', 'hive', 'normalizado']
) as dag:

    cargar_modelo_task = PythonOperator(
        task_id='cargar_modelo_normalizado',
        python_callable=cargar_modelo_normalizado_hive
    )
