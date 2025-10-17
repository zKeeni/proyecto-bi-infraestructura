#AAAA
from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime
import pandas as pd
from pyhive import hive
import logging
import chardet
import csv
import os

# Ruta de datos
CSV_PATH = '/opt/airflow/dags/data/productos_mas_exportados.csv'

# ------------------ FUNCIONES AUXILIARES ------------------ #
def detectar_codificacion(csv_path):
    with open(csv_path, 'rb') as f:
        raw = f.read()
        resultado = chardet.detect(raw)
        return resultado['encoding']

def transformar_datos(csv_path):
    """Transforma CSV con datos de exportaciones anuales por producto."""
    encoding = detectar_codificacion(csv_path)
    codificaciones = [encoding, 'utf-8', 'latin-1', 'iso-8859-1', 'cp1252']
    filas = []
    for enc in codificaciones:
        try:
            with open(csv_path, 'r', encoding=enc) as f:
                reader = csv.reader(f, delimiter='\t')
                filas = [r for r in reader if any(r)]
            if len(filas) > 2:
                break
        except Exception:
            continue
    if not filas:
        raise ValueError("No se pudo leer el archivo CSV con ninguna codificación.")

    años = filas[0][1:]
    metricas = filas[1][1:]
    columnas = ['Producto']
    for año, metrica in zip(años, metricas):
        columnas.append(f"{año}_{metrica}".replace(' ', '_').replace('(', '').replace(')', ''))
    df = pd.DataFrame(filas[2:], columns=columnas)

    datos_transformados = []
    for _, row in df.iterrows():
        producto = row['Producto'].strip()
        for year in range(2021, 2026):
            peso_col = f"{year}_Peso_t"
            fob_col = f"{year}_FOB_USD_miles"
            if peso_col in row and fob_col in row:
                try:
                    peso = float(str(row[peso_col]).replace('.', '').replace(',', '.'))
                    fob = float(str(row[fob_col]).replace('.', '').replace(',', '.'))
                    datos_transformados.append({
                        'producto': producto,
                        'anio': year,
                        'peso_toneladas': peso,
                        'valor_fob_miles_usd': fob
                    })
                except Exception:
                    continue
    df_transformado = pd.DataFrame(datos_transformados)
    logging.info(f"Datos transformados: {len(df_transformado)} registros")
    return df_transformado

# ------------------ CARGA A HIVE ------------------ #
def cargar_modelo_bi():
    if not os.path.exists(CSV_PATH):
        raise FileNotFoundError(f"No se encuentra el archivo: {CSV_PATH}")

    df = transformar_datos(CSV_PATH)
    if df.empty:
        raise ValueError("El DataFrame transformado está vacío, no se cargará nada.")

    conn = hive.Connection(host='hiveserver2', port=10000, username='hive')
    cursor = conn.cursor()

    # ✅ DESPUÉS (BUENO):
    logging.info("Usando base de datos cacao...")
    cursor.execute("CREATE DATABASE IF NOT EXISTS cacao")
    cursor.execute("USE cacao")

    # Ahora sí, DROP de las tablas específicas de este script
    cursor.execute("DROP TABLE IF EXISTS dim_producto")
    cursor.execute("DROP TABLE IF EXISTS fact_exportaciones")

    # --- Tabla de productos ---
    cursor.execute("""
        CREATE TABLE dim_producto (
            producto_id STRING,
            nombre_producto STRING,
            categoria STRING,
            unidad_medida STRING,
            CONSTRAINT pk_producto PRIMARY KEY (producto_id) DISABLE NOVALIDATE RELY
        ) STORED AS PARQUET
    """)

    # --- Tabla de hechos ---
    cursor.execute("""
        CREATE TABLE fact_exportaciones (
            id_exportacion BIGINT,
            producto_id STRING,
            anio INT,
            peso_toneladas DOUBLE,
            valor_fob_miles_usd DOUBLE,
            CONSTRAINT pk_fact_export PRIMARY KEY (id_exportacion) DISABLE NOVALIDATE RELY,
            CONSTRAINT fk_fact_producto FOREIGN KEY (producto_id) REFERENCES dim_producto(producto_id) DISABLE NOVALIDATE RELY
        ) STORED AS PARQUET
    """)

    # --- Poblar dim_producto ---
    productos_unicos = df['producto'].drop_duplicates()
    for i, producto in enumerate(productos_unicos, 1):
        categoria = "Otros"
        p = producto.lower()
        if 'cacao' in p: categoria = "Cacao"
        elif 'banano' in p: categoria = "Banano"
        elif 'cafe' in p: categoria = "Café"
        elif 'madera' in p: categoria = "Madera"
        elif 'palma' in p: categoria = "Aceite de Palma"
        elif 'rosa' in p or 'flor' in p: categoria = "Flores"
        producto_sql = producto.replace("'", "''")
        cursor.execute(f"""
            INSERT INTO TABLE dim_producto
            VALUES ('P{i:03d}', '{producto_sql}', '{categoria}', 'Toneladas')
        """)

    # --- Poblar fact_exportaciones ---
    for i, row in df.iterrows():
        producto = row['producto']
        anio = row['anio']
        peso = row['peso_toneladas']
        fob = row['valor_fob_miles_usd']
        producto_id = f"P{list(productos_unicos).index(producto)+1:03d}"
        cursor.execute(f"""
            INSERT INTO TABLE fact_exportaciones
            VALUES ({i+1}, '{producto_id}', {anio}, {peso}, {fob})
        """)

    conn.close()
    logging.info("Carga del modelo BI completada con éxito ✅")


# ------------------ DAG DE AIRFLOW ------------------ #
with DAG(
    dag_id='cargar_fact_productos_exportados',
    description='Crea modelo BI (Star Schema) para exportaciones y carga datos a Hive',
    start_date=datetime(2025, 10, 5),
    catchup=False,
    schedule=None,
    tags=['bi', 'hive', 'exportaciones', 'cacao']
) as dag:

    cargar_modelo_bi_task = PythonOperator(
        task_id='cargar_modelo_bi',
        python_callable=cargar_modelo_bi
    )
