# 🌱 Proyecto BI – Infraestructura de Análisis del Cacao Ecuatoriano

Este repositorio contiene la configuración de infraestructura para un proyecto de **Business Intelligence (BI)** orientado al análisis de datos de exportación de **cacao ecuatoriano**.  
El entorno se basa en **contenedores Docker**, integrando herramientas de orquestación, almacenamiento y visualización de datos.

---

## 🧰 Tecnologías Utilizadas

- **Apache Airflow** – Orquestación de flujos ETL  
- **Apache Hive** – Almacenamiento y procesamiento de datos  
- **Redash** – Visualización y dashboards interactivos  
- **Docker Compose** – Gestión de contenedores y redes  

---

## ⚙️ Requisitos Previos

Antes de comenzar, asegúrate de tener instalado **Docker** y **Docker Compose** en tu sistema.

📘 [Instalar Docker](https://docs.docker.com/get-docker/)  
📘 [Instalar Docker Compose](https://docs.docker.com/compose/install/)

---

## 🚀 Instrucciones de Instalación

### 1️⃣ Clonar el repositorio
```bash
git clone https://github.com/zKeeni/proyecto-bi-infra.git
```
Acceda al directorio de la carpeta clonada
```bash
cd proyecto-bi-infra
```
### 2️⃣ Configurar Apache Airflow
```bash
cd airflow
```

Crear directorios necesarios:
```bash
mkdir -p logs plugins
```
(Estos directorios son ignorados por Git y deben crearse localmente para que Airflow funcione correctamente.)

Levantar los contenedores:
```bash
docker compose up -d
```

Airflow quedará disponible en:
👉 http://localhost:8080

### 3️⃣ Configurar Apache Hive
```bash
cd ../hive
```

Crear los directorios de datos:
```bash
mkdir -p hdfs hive-logs hive_warehouse postgres_data
```

Asignar permisos (si es necesario):
```bash
sudo chmod -R 777 hdfs hive-logs hive_warehouse postgres_data
```

Levantar los contenedores:
```bash
docker compose up -d
```

Hive Server2 estará disponible en el puerto configurado (por defecto: 10000).

### 4️⃣ Configurar Redash
```bash
cd ../redash
```

Crear el archivo .env:
Ejemplo de configuración funcional (ya incluida en este repositorio):

```env
# Claves internas de Redash
REDASH_SECRET_KEY=supersecretkey
REDASH_COOKIE_SECRET=anothersecretkey

# Base de datos de Redash
POSTGRES_PASSWORD=postgres
REDASH_DATABASE_URL=postgresql://postgres:postgres@redash_postgres/postgres

# Redis (tareas en segundo plano)
REDASH_REDIS_URL=redis://redis:6379/0
```

💡 Puedes cambiar estas claves si deseas mayor seguridad, pero recuerda actualizar el docker-compose.yml en consecuencia.

Levantar Redash:
```bash
docker compose up -d
```

Una vez iniciado, Redash estará disponible en:
👉 http://localhost:5000
