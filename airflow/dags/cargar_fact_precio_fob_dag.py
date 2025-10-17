##pp23
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
from pyhive import hive
import logging
import os

# --- CONFIGURACIÓN DE CONEXIÓN Y RUTAS ---
HIVE_HOST = 'hiveserver2'
HIVE_PORT = 10000
DB_NAME = 'cacao'
HIVE_USER = 'hive'

# Archivos CSV de origen
PRECIO_2024_CSV = '/opt/airflow/dags/data/precio_fob_exportaciones_cacao_2024.csv'
PRECIO_2025_CSV = '/opt/airflow/dags/data/precio_fob_exportaciones_cacao_2025.csv'
CSV_SEP = ';'

# ==========================
# FUNCIONES AUXILIARES
# ==========================

def limpiar_columnas(df):
    """Convierte nombres de columnas a minúsculas, con _ y sin tildes."""
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('á', 'a')
        .str.replace('é', 'e')
        .str.replace('í', 'i')
        .str.replace('ó', 'o')
        .str.replace('ú', 'u')
    )
    return df

def leer_csv(file_path):
    """Lee un CSV delimitado por ; con coma como decimal."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"No se encuentra el archivo: {file_path}")
    df = pd.read_csv(file_path, sep=CSV_SEP, decimal=',', encoding='utf-8')
    return limpiar_columnas(df)

def insertar_fila_hive(cursor, table_name, row):
    """Inserta una fila en una tabla Hive."""
    valores = []
    for val in row:
        if isinstance(val, (int, float)):
            valores.append(str(val))
        elif isinstance(val, str):
            valores.append(f"'{val.replace("'", "''")}'")
        else:
            valores.append('NULL')
    cursor.execute(f"INSERT INTO TABLE {DB_NAME}.{table_name} VALUES ({', '.join(valores)})")

# ==========================
# CARGA PRINCIPAL
# ==========================
def cargar_precios_fob_hive():
    """Lee, normaliza y carga los precios FOB del cacao en Hive."""
    # 1. Leer los CSV
    df_2024 = leer_csv(PRECIO_2024_CSV)
    df_2025 = leer_csv(PRECIO_2025_CSV)
    df = pd.concat([df_2024, df_2025], ignore_index=True)
    df = df.fillna(0)

    # 2. Validar columnas requeridas
    requeridas = ['anio', 'mes', 'semana', 'cacao_grado_1', 'cacao_grado_2', 'cacao_grado_3']
    for col in requeridas:
        if col not in df.columns:
            raise ValueError(f"Falta columna requerida: {col}")

    # 3. Crear tablas normalizadas
    # --- Dimensión periodo_precio (RENOMBRADO) ---
    dim_periodo_precio = df[['anio', 'mes']].drop_duplicates().reset_index(drop=True)
    dim_periodo_precio.insert(0, 'id_periodo_precio', range(1, len(dim_periodo_precio) + 1))

    # --- Dimensión grado ---
    dim_grado = pd.DataFrame({
        'id_grado': [1, 2, 3],
        'nombre_grado': ['Cacao_Grado_1', 'Cacao_Grado_2', 'Cacao_Grado_3']
    })


    # --- Tabla de hechos ---
    fact_rows = []
    for _, fila in df.iterrows():
        id_periodo_precio = dim_periodo_precio.loc[
            (dim_periodo_precio['anio'] == fila['anio']) & (dim_periodo_precio['mes'] == fila['mes']),
            'id_periodo_precio'
        ].values[0]
        for i, col in enumerate(['cacao_grado_1', 'cacao_grado_2', 'cacao_grado_3'], start=1):
            fact_rows.append({
                'id_periodo_precio': id_periodo_precio,
                'id_grado': i,
                'semana': fila['semana'],
                'valor_fob': fila[col]
            })
    fact_precios = pd.DataFrame(fact_rows)
    fact_precios.insert(0, 'id_precio', range(1, len(fact_precios) + 1))

    # 4. Conexión a Hive
    conn = hive.Connection(host=HIVE_HOST, port=HIVE_PORT, username=HIVE_USER)
    cursor = conn.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")

    # 5. Crear tablas en Hive (TABLA RENOMBRADA)
    cursor.execute("DROP TABLE IF EXISTS dim_periodo_precio")
    cursor.execute("""
        CREATE TABLE dim_periodo_precio (
            id_periodo_precio INT,
            anio INT,
            mes STRING
        ) STORED AS PARQUET
    """)

    cursor.execute("DROP TABLE IF EXISTS dim_grado")
    cursor.execute("""
        CREATE TABLE dim_grado (
            id_grado INT,
            nombre_grado STRING
        ) STORED AS PARQUET
    """)

    cursor.execute("DROP TABLE IF EXISTS fact_precios_fob")
    cursor.execute("""
        CREATE TABLE fact_precios_fob (
            id_precio BIGINT,
            id_periodo_precio INT,
            id_grado INT,
            semana INT,
            valor_fob DOUBLE
        ) STORED AS PARQUET
    """)

    # 6. Insertar datos
    for _, row in dim_periodo_precio.iterrows():
        insertar_fila_hive(cursor, 'dim_periodo_precio', row)

    for _, row in dim_grado.iterrows():
        insertar_fila_hive(cursor, 'dim_grado', row)

    for _, row in fact_precios.iterrows():
        insertar_fila_hive(cursor, 'fact_precios_fob', row)

    conn.close()
    logging.info("Carga de precios FOB normalizados completada ✅")

# ==========================
# DAG DE AIRFLOW
# ==========================
with DAG(
    dag_id='cargar_fact_precio_fob',
    description='Carga datos normalizados de precios FOB de cacao en Hive',
    start_date=datetime(2025, 10, 11),
    catchup=False,
    schedule=None,
    tags=['hive', 'etl', 'cacao']
) as dag:

    cargar_precios_task = PythonOperator(
        task_id='cargar_precios_fob',
        python_callable=cargar_precios_fob_hive
    )
