##ppepe2
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
from pyhive import hive 
import logging
import os
import re

# --- Configuración y Conexión ---
CSV_PATH = '/opt/airflow/dags/data/superficie_produccion_ventas_cacao_2024.csv'
HIVE_HOST = 'hiveserver2'
HIVE_PORT = 10000
DB_NAME = 'cacao'
HIVE_USER = 'hive'


# ------------------ FUNCIONES DE TRANSFORMACIÓN ------------------ #
def transformar_produccion(file_path):
    """Transforma el archivo de Producción/Superficie."""
    logging.info(f"Iniciando transformación del archivo: {file_path}")
    
    try:
        df = pd.read_csv(file_path, header=None, skiprows=2, sep=';', encoding='latin-1')
    except Exception as e:
        logging.error(f"Error al leer el CSV: {e}")
        raise

    meaningful_columns = [
        'Region_raw', 'Provincia_raw', 'Tipo_Cultivo_raw',
        'Sup_Plantada_Ha', 'Sup_Cosechada_Ha', 'Produccion_Tm', 'Ventas_Tm'
    ]
    
    df = df.iloc[:, :len(meaningful_columns)].copy()
    df.columns = meaningful_columns
    df = df.iloc[1:].copy()

    df['Region'] = df['Region_raw'].mask(df['Provincia_raw'].isna()).ffill()
    df['Provincia'] = df['Provincia_raw'].ffill()

    numeric_cols = ['Sup_Plantada_Ha', 'Sup_Cosechada_Ha', 'Produccion_Tm', 'Ventas_Tm']
    for col in numeric_cols:
        df[col] = df[col].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    df_final = df[
        ['Region', 'Provincia', 'Tipo_Cultivo_raw'] + numeric_cols
    ].rename(columns={'Tipo_Cultivo_raw': 'Tipo_Cultivo'}).dropna(subset=['Produccion_Tm', 'Provincia'])
    
    df_final['Region'] = df_final['Region'].str.strip()
    df_final['Provincia'] = df_final['Provincia'].str.strip()
    
    logging.info(f"Datos transformados: {len(df_final)} registros.")
    return df_final


# ------------------ FUNCIÓN DE CARGA A HIVE ------------------ #
def cargar_produccion_hive():
    """Transforma el archivo y carga los datos en tablas normalizadas en Hive."""
    
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"No se encuentra el archivo: {CSV_PATH}")

    df = transformar_produccion(CSV_PATH)
    if df.empty:
        logging.warning("El DataFrame transformado está vacío. No se cargará nada.")
        return

    conn = hive.Connection(host=HIVE_HOST, port=HIVE_PORT, username=HIVE_USER)
    cursor = conn.cursor()

    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")

    # --- Crear tablas ---
    cursor.execute("DROP TABLE IF EXISTS fact_produccion_superficie")
    cursor.execute("DROP TABLE IF EXISTS dim_provincia")
    cursor.execute("DROP TABLE IF EXISTS dim_tipo_cultivo")

    cursor.execute("""
        CREATE TABLE dim_provincia (
            id_provincia STRING,
            nombre_provincia STRING,
            region STRING
        ) STORED AS PARQUET
    """)

    cursor.execute("""
        CREATE TABLE dim_tipo_cultivo (
            id_tipo_cultivo STRING,
            nombre_tipo_cultivo STRING
        ) STORED AS PARQUET
    """)

    cursor.execute("""
        CREATE TABLE fact_produccion_superficie (
            id_registro BIGINT,
            id_provincia STRING,
            id_tipo_cultivo STRING,
            sup_plantada_ha DOUBLE,
            sup_cosechada_ha DOUBLE,
            produccion_tm DOUBLE,
            ventas_tm DOUBLE
        ) STORED AS PARQUET
    """)

    # --- Generar data para las tablas ---
    provincias_unicas = df[['Provincia', 'Region']].drop_duplicates().reset_index(drop=True)
    provincias_unicas['id_provincia'] = ['PRV{:03d}'.format(i+1) for i in range(len(provincias_unicas))]

    tipos_unicos = df['Tipo_Cultivo'].drop_duplicates().reset_index(drop=True)
    tipos_unicos = pd.DataFrame({
        'id_tipo_cultivo': ['TC{:03d}'.format(i+1) for i in range(len(tipos_unicos))],
        'nombre_tipo_cultivo': tipos_unicos
    })

    df = df.merge(provincias_unicas, on=['Provincia', 'Region'], how='left')
    df = df.merge(tipos_unicos, left_on='Tipo_Cultivo', right_on='nombre_tipo_cultivo', how='left')
    df['id_registro'] = range(1, len(df) + 1)

    # --- Cargar en Hive con INSERTs directos (sin LOAD DATA) ---
    logging.info("Insertando datos en Hive...")

    # Provincias
    for _, row in provincias_unicas.iterrows():
        cursor.execute(f"""
            INSERT INTO dim_provincia VALUES (
                '{row['id_provincia']}',
                '{row['Provincia'].replace("'", "''")}',
                '{row['Region'].replace("'", "''")}'
            )
        """)

    # Tipos de cultivo
    for _, row in tipos_unicos.iterrows():
        cursor.execute(f"""
            INSERT INTO dim_tipo_cultivo VALUES (
                '{row['id_tipo_cultivo']}',
                '{row['nombre_tipo_cultivo'].replace("'", "''")}'
            )
        """)

    # Tabla de hechos
    for _, row in df.iterrows():
        cursor.execute(f"""
            INSERT INTO fact_produccion_superficie VALUES (
                {row['id_registro']},
                '{row['id_provincia']}',
                '{row['id_tipo_cultivo']}',
                {row['Sup_Plantada_Ha'] if pd.notnull(row['Sup_Plantada_Ha']) else 'NULL'},
                {row['Sup_Cosechada_Ha'] if pd.notnull(row['Sup_Cosechada_Ha']) else 'NULL'},
                {row['Produccion_Tm'] if pd.notnull(row['Produccion_Tm']) else 'NULL'},
                {row['Ventas_Tm'] if pd.notnull(row['Ventas_Tm']) else 'NULL'}
            )
        """)

    conn.close()
    logging.info("Carga de datos a Hive completada con éxito ✅")


# ------------------ DAG DE AIRFLOW ------------------ #
with DAG(
    dag_id='cargar_fact_produccion_superficie',
    description='ETL para data de Producción y Superficie a Hive (Context Table)',
    start_date=datetime(2025, 10, 5),
    catchup=False,
    schedule=None,
    tags=['hive', 'produccion']
) as dag:

    cargar_produccion_task = PythonOperator(
        task_id='cargar_datos_produccion',
        python_callable=cargar_produccion_hive
    )

