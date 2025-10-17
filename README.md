# 🌱 Proyecto BI – Infraestructura de Análisis del Cacao Ecuatoriano

Este repositorio contiene la configuración de infraestructura para un proyecto de **Business Intelligence (BI)** orientado al análisis de datos de exportación de **cacao ecuatoriano**.  
El entorno se basa en **contenedores Docker**, integrando herramientas de orquestación, almacenamiento y visualización de datos.

---

## 💻 Entorno de Ejecución

Este proyecto fue desarrollado y probado en un entorno **Linux (Ubuntu 24.04)**.  
Si te encuentras en **Windows**, puedes usar **WSL (Windows Subsystem for Linux)** para ejecutar el proyecto.

### 🧩 Instalación de WSL en Windows
1. Abre **PowerShell como administrador** y ejecuta:
   ```bash
   wsl --install
   ```
2. Reinicia tu computadora cuando el sistema lo solicite.
3. Al volver a iniciar, selecciona Ubuntu como distribución predeterminada (o instálala desde Microsoft Store).
4. Luego abre tu terminal de Ubuntu desde Windows y continúa con las instrucciones de este README desde allí.

⚙️ Requisitos del Sistema

Para ejecutar correctamente todo el entorno (Airflow + Hive + Redash), se recomienda contar con un equipo con recursos suficientes para soportar la carga de los tres contenedores.

Requisitos mínimos:

💻 Procesador: Intel Core i7 (10.ª generación o superior)

🧠 Memoria RAM: 16 GB

🐧 Sistema operativo: Linux nativo o WSL2 con Ubuntu 22.04 o superior

💾 Almacenamiento: El espacio necesario dependerá del tamaño de los datos y de los contenedores; WSL o Linux gestionan esto internamente.

Equipo en el que se probó el proyecto:

💻 Procesador: Intel Core i9 (13.ª generación)

🧠 Memoria RAM: 32 GB

>⚠️ Recomendación:
Durante las pruebas, el entorno completo llegó a utilizar más de 16 GB de RAM.
Si tu equipo cuenta con 16 GB, es posible que notes lentitud o sobrecarga al ejecutar los tres contenedores simultáneamente.
En ese caso, se sugiere disponer de más memoria o levantar los servicios por separado.

El espacio en disco lo gestiona internamente WSL o el sistema Linux.

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

##🧩 Instalación y Configuración

### 1️⃣ Clonar el repositorio
```bash
git clone https://github.com/zKeeni/proyecto-bi-infraestructura.git
```
Acceda al directorio de la carpeta clonada
```bash
cd proyecto-bi-infraestructura/
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
cd compose/
```
```bash
docker compose up -d
```

Hive Server2 estará disponible en el puerto configurado (por defecto: 10000).

### 4️⃣ Configurar Redash
```bash
cd ../../redash
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

Si desea ocupar esta misma configuración ya incluida, entonces cambie el nombre del archivo de ejemplo a .env
```bash
mv .env.example .env
```


💡 Puedes cambiar estas claves si deseas mayor seguridad, pero recuerda actualizar el docker-compose.yml en consecuencia.

Levantar Redash:
```bash
docker compose up -d
```

Una vez iniciado, Redash estará disponible en:
👉 http://localhost:5000
--- 
## 🧠 Uso del Proyecto

Una vez que los tres servicios estén activos (Airflow, Hive y Redash), sigue los pasos a continuación para ejecutar los procesos ETL y visualizar los dashboards.

### 🪶 En Airflow

1. Abre Airflow:
👉 http://localhost:8080/dags

2. En la barra de búsqueda, escribe cargar para listar los DAGs del proyecto.
Deberás ver los DAGs similares a la siguiente imagen
<img width="1919" height="1137" alt="image" src="https://github.com/user-attachments/assets/9bc61b0d-4f5b-46ba-8e7c-c12cc88ebdc9" />

Ejecuta los DAGs en el siguiente orden:

🗃️ Tras ejecutar estos DAGs, la base de datos cacao se escribirá dentro de Hive.
Asegúrate de tener ambos contenedores (Airflow y Hive) levantados

### 📊 En Redash

1. Abre Redash:
👉 http://localhost:5000

2. Ingresa las siguientes credenciales:
Usuario: admin@email.com
Contraseña: admin123

Una vez dentro del panel de control, accede a Dashboards.

Podrás refrescar los dashboards con la información cargada desde Hive.

🔗 En Redash, toda la configuración de conexión, consultas SQL y dashboards ya está preconfigurada.
Solo asegúrate de que los pasos de Airflow y Hive se hayan ejecutado correctamente para evitar errores de datos inexistentes.
