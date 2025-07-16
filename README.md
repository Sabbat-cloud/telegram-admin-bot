# telegram-admin-bot
Friendly and reasonably simple telegram bot.

## 📜 Licencia

Este proyecto está bajo la Licencia MIT. Ver el fichero `LICENSE` para más detalles.

## Versión en Español es
🔧 Instalación
Existen dos métodos para instalar y ejecutar el bot. La instalación con Docker es la recomendada por su simplicidad y fiabilidad.

### Método 1: Instalación Clásica (Manual)
Este método es ideal si no quieres usar Docker y prefieres gestionar el entorno manualmente.

1. Prerrequisitos del Sistema

Asegúrate de tener todo lo necesario instalado:

Bash

# Para sistemas basados en Debian/Ubuntu
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git nmap traceroute
2. Clonar el Repositorio

Bash

git clone https://github.com/tu-usuario/telegram-admin-bot.git
cd telegram-admin-bot
(Reemplaza la URL por la de tu repositorio)

3. Configurar el Bot

Copia la plantilla de configuración y edítala con tus datos (el token de tu bot, tu ID de usuario de Telegram, etc.).

Bash

cp config/config.json.template config/config.json
nano config/config.json
4. Preparar el Entorno de Python

Crea un entorno virtual e instala las dependencias del proyecto.

Bash

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
5. Ejecutar el Bot

Bash

python3 bot/bot.py
El bot comenzará a funcionar. Para detenerlo, presiona Ctrl+C. Para un uso en producción, se recomienda ejecutarlo como un servicio de systemd o dentro de una sesión de tmux.

### Método 2: Instalación con Docker (Recomendado)
Este método encapsula el bot y todas sus dependencias en un contenedor, asegurando que funcione en cualquier sistema con Docker.

1. Prerrequisitos del Sistema

Solo necesitas tener Docker y Docker Compose instalados. Consulta la guía oficial de Docker para instalarlos.

2. Clonar el Repositorio

Bash

git clone https://github.com/tu-usuario/telegram-admin-bot.git
cd telegram-admin-bot
(Reemplaza la URL por la de tu repositorio)

3. Configurar el Bot

Copia la plantilla de configuración y edítala con tus datos.

Bash

cp config/config.json.template config/config.json
nano config/config.json
Importante: Asegúrate de que las rutas dentro del fichero (image_directory, file_directory) usen la ruta base del contenedor, por ejemplo: "/app/data/imagenes".

4. Crear Directorios de Datos

Crea las carpetas en tu máquina local donde el bot guardará los archivos.

Bash

mkdir -p data/imagenes data/ficheros
5. Levantar el Contenedor

Construye la imagen y ejecuta el contenedor en segundo plano (-d).

Bash

docker-compose up --build -d
El bot ya está funcionando. Para ver los logs en tiempo real, usa docker-compose logs -f. Para detener el bot, ejecuta docker-compose down.

## English Version gb
🔧 Installation
There are two methods to install and run the bot. The Docker installation is recommended for its simplicity and reliability.

### Method 1: Classic Installation (Manual)
This method is ideal if you prefer not to use Docker and wish to manage the environment manually.

1. System Prerequisites

Ensure you have all the necessary tools installed:

Bash

# For Debian/Ubuntu-based systems
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git nmap traceroute
2. Clone the Repository

Bash

git clone https://github.com/your-username/telegram-admin-bot.git
cd telegram-admin-bot
(Replace the URL with your repository's URL)

3. Configure the Bot

Copy the configuration template and edit it with your data (your bot token, your Telegram user ID, etc.).

Bash

cp config/config.json.template config/config.json
nano config/config.json
4. Set up the Python Environment

Create a virtual environment and install the project's dependencies.

Bash

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
5. Run the Bot

Bash

python3 bot/bot.py
The bot will start running. To stop it, press Ctrl+C. For production use, it's recommended to run it as a systemd service or within a tmux session.

### Method 2: Docker Installation (Recommended)
This method packages the bot and all its dependencies into a container, ensuring it works on any system with Docker installed.

1. System Prerequisites

You only need Docker and Docker Compose. Refer to the official Docker guide for installation instructions.

2. Clone the Repository

Bash

git clone https://github.com/your-username/telegram-admin-bot.git
cd telegram-admin-bot
(Replace the URL with your repository's URL)

3. Configure the Bot

Copy the configuration template and edit it with your data.

Bash

cp config/config.json.template config/config.json
nano config/config.json
Important: Make sure the paths inside the file (image_directory, file_directory) use the container's base path, for example: "/app/data/imagenes".

4. Create Data Directories

Create the folders on your local machine where the bot will store files.

Bash

mkdir -p data/imagenes data/ficheros
5. Run the Container

Build the image and run the container in detached mode (-d).

Bash

docker-compose up --build -d
The bot is now running. To view the logs in real-time, use docker-compose logs -f. To stop the bot, run docker-compose down.
