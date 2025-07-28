**Versión en Español**](#versión-en-español) | [**English Version**](#english-version)

---

## Versión en Español

# Telegram SysAdmin Bot

Un potente bot de Telegram para la administración y monitorización remota de servidores Linux, con integración de IA a través de la API de Gemini.

---

### 🌟 Características

- **Monitorización del Sistema**: CPU, RAM, disco, procesos, etc.
- **Gestión Remota**: Inicia/para/reinicia servicios (`systemctl`) y contenedores Docker.
- **Herramientas de Red**: `ping`, `nmap`, `traceroute`, `dig`, `whois`.
- **Inteligencia Artificial**:
  - `ask`: Haz preguntas generales.
  - `analyze`: Pide a la IA que analice datos del sistema (`ps aux`, `df -h`, etc.) y te dé recomendaciones.
- **Gestión de Ficheros**: Sube y descarga ficheros directamente desde el chat.
- **Scripts y Backups**: Ejecuta scripts predefinidos de forma segura.
- **Seguridad**: Acceso restringido a usuarios autorizados y super-administrador.
- **Internacionalización**: Soporte para múltiples idiomas (inglés y español por defecto).
- **Notificaciones**: Alertas periódicas de estado y recordatorios personalizables.
- **Seguridad Proactiva**: Alertas en tiempo real por patrones en logs e integración con `Fail2Ban` para gestionar IPs bloqueadas.
- **Protección Anti-Flood**: El bot ignora comandos repetidos en un corto periodo de tiempo para prevenir el spam y la sobrecarga.

### 🚀 Arquitectura y Rendimiento

El bot está construido sobre una base asíncrona (`asyncio`) para máxima eficiencia. Todas las operaciones que podrían tardar (como escaneos de red con `nmap`, consultas a la IA de Gemini, o la ejecución de backups) se delegan a un hilo de trabajo separado usando `asyncio.to_thread`.

Esto asegura que el bot nunca se quede "bloqueado" y pueda seguir respondiendo a múltiples usuarios y comandos simultáneamente, sin importar la carga de trabajo en segundo plano.

El bot tiene una capa antiflood para evitar la saturación de mensajes, ya sea de forma intencionada como accidental.

Repositorio de imágenes y ficheros. Por defecto guardara cualquier imagen o fichero que se añada en las carpetas correspondientes.

---

### 🔧 Prerrequisitos

Asegúrate de tener instalados los siguientes componentes en el servidor donde se ejecutará el bot.

1.  **Dependencias del Sistema**:
    ```bash
    sudo apt update
    sudo apt install python3 python3-pip python3-venv git fortune nmap traceroute dnsutils whois
    ```
    - `ansiweather`: Para la consulta del tiempo. Se instala de forma distinta, consulta su repositorio.

2.  **Git** para clonar el repositorio.

---

### ⚙️ Instalación

1.  **Clona el repositorio**:
    ```bash
    git clone <URL_DEL_REPOSITORIO>
    cd <NOMBRE_DEL_DIRECTORIO>
    ```

2.  **Crea y activa un entorno virtual** (recomendado):
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Instala las dependencias de Python**:
    ```bash
    pip install python-telegram-bot[job-queue] google-generativeai psutil
    ```

---

### 🚀 Configuración

La configuración se ha separado para mejorar la seguridad.

#### 1. Variables de Entorno (Secretos)
Crea un fichero `.env` en la raíz del proyecto o exporta las variables directamente.
```bash
# Fichero: .env
TELEGRAM_TOKEN="12345:ABCDEFGHIJKLMN-OPQRSTUVWXYZ"
GEMINI_API_KEY="AIzaSy...RESTO_DE_TU_API_KEY"
2. Fichero de Usuarios (users.json)
Crea el fichero users.json. Necesitarás saber tu ID de usuario de Telegram para configurarte como super-admin.

{
  "super_admin_id": 123456789,
  "authorized_users": [
    123456789,
    987654321
  ]
}
3. Fichero de Configuración (configbot.json.example)
Edita configbot.json.example y renombra a configbot.json para definir las rutas a tus scripts, los servicios que quieres gestionar, los servidores a monitorizar, etc. Los secretos ya no se guardan aquí.

4. Permisos de sudo
El bot necesita permisos para reiniciar servicios o contenedores. Esto es crítico para la seguridad. Edita el fichero de sudoers con sudo visudo y añade líneas específicas para el usuario que ejecutará el bot, NUNCA le des acceso sin contraseña a todo.

# /etc/sudoers
# Reemplaza 'usuario_bot' por el nombre de usuario real
usuario_bot ALL=(ALL) NOPASSWD: /usr/bin/systemctl start nginx, /usr/bin/systemctl stop nginx, /usr/bin/systemctl restart nginx, /usr/bin/docker restart mi_container
5. Configuración de Fail2Ban y Monitorización de Logs
Añade las siguientes secciones a tu configbot.json para habilitar estas características:

fail2ban_jails: Una lista de las jaulas (jails) en las que el comando unban debe buscar.
log_monitoring: Activa la vigilancia de logs, define el intervalo de revisión y los ficheros y patrones a buscar.
▶️ Ejecución Manual
Para pruebas o ejecución directa en tu terminal.

Asegúrate de haber activado el entorno virtual (source venv/bin/activate).
Exporta las variables de entorno si no usas un sistema que las cargue automáticamente.
export TELEGRAM_TOKEN="TU_TOKEN"
export GEMINI_API_KEY="TU_API_KEY"
Ejecuta el bot:
python3 bot_interactivo.py
⚙️ Ejecución como Servicio (Daemon) con systemd
Para que el bot se ejecute de forma continua en segundo plano y se inicie automáticamente con el sistema, debes configurarlo como un servicio de systemd.

Paso 1: Crear el Fichero de Entorno para el Servicio
El servicio de systemd se ejecuta en un entorno aislado y no puede ver las variables que exportas en tu terminal. Por ello, es necesario crear un fichero específico para ellas.

Crea un directorio de configuración para el bot:

sudo mkdir -p /etc/telegram-bot
Crea el fichero de entorno con tus secretos:

sudo nano /etc/telegram-bot/bot.env
Añade el siguiente contenido, sin comillas:

# /etc/telegram-bot/bot.env
TELEGRAM_TOKEN=TU_TOKEN_DE_TELEGRAM
GEMINI_API_KEY=TU_API_KEY_DE_GEMINI
Paso 2: Proteger el Fichero de Entorno 🛡️
Asegura que solo el usuario que ejecuta el bot (y root) pueda leer este fichero. Reemplaza tu_usuario con el nombre de usuario que usará el servicio.

sudo chown tu_usuario:tu_usuario /etc/telegram-bot/bot.env
sudo chmod 600 /etc/telegram-bot/bot.env
Paso 3: Crear el Fichero del Servicio systemd
Este fichero define cómo systemd debe gestionar tu bot.

Crea el fichero de servicio:

sudo nano /etc/systemd/system/telegram-bot.service
Pega el siguiente contenido. Presta especial atención a User, WorkingDirectory y ExecStart y modifícalos según tu configuración.

[Unit]
Description=Bot de Telegram para SysAdmin
# Se asegura de que la red esté disponible antes de iniciar
After=network.target

[Service]
# Reemplaza 'tu_usuario' con el usuario que ejecutará el script
User=tu_usuario
Group=tu_usuario

# Reemplaza con la ruta absoluta al directorio de tu bot
WorkingDirectory=/home/tu_usuario/telegram_bot

# --- Elige UNA de las siguientes líneas ExecStart ---

# OPCIÓN A: Si usas un ENTORNO VIRTUAL (Recomendado)
# Reemplaza con la ruta completa al python de tu venv
ExecStart=/home/tu_usuario/telegram_bot/venv/bin/python3 /home/tu_usuario/telegram_bot/bot_interactivo.py

# OPCIÓN B: Si NO usas entorno virtual
# Descomenta esta línea y comenta la anterior
# ExecStart=/usr/bin/python3 /home/tu_usuario/telegram_bot/bot_interactivo.py

# Carga las variables de entorno desde el fichero que creamos
EnvironmentFile=/etc/telegram-bot/bot.env

# Reinicia el servicio si falla
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
Paso 4: Gestionar el Servicio
Una vez guardado el fichero .service, usa los siguientes comandos para controlar tu nuevo daemon:

Recargar systemd para que detecte el nuevo servicio:
sudo systemctl daemon-reload
Habilitar el servicio para que se inicie al arrancar el sistema:
sudo systemctl enable telegram-bot.service
Iniciar el servicio ahora mismo:
sudo systemctl start telegram-bot.service
Comprobar el estado para ver si está corriendo y si hay errores:
sudo systemctl status telegram-bot.service
Para parar el servicio: sudo systemctl stop telegram-bot.service
Para reiniciarlo después de un cambio: sudo systemctl restart telegram-bot.service
🌐 Localización
El bot usa gettext para la traducción.

Para añadir un nuevo idioma o actualizar traducciones, edita los ficheros .po en locales/<idioma>/LC_MESSAGES/.
Después de editar, compila el fichero .po a formato .mo:
msgfmt -o locales/es/LC_MESSAGES/base.mo locales/es/LC_MESSAGES/base.po
English Version
Telegram SysAdmin Bot
A powerful Telegram bot for remote administration and monitoring of Linux servers, with AI integration through the Gemini API.

🌟 Features
System Monitoring: CPU, RAM, disk, processes, etc.
Remote Management: Start/stop/restart services (systemctl) and Docker containers.
Network Tools: ping, nmap, traceroute, dig, whois.
Artificial Intelligence:
ask: Ask general questions.
analyze: Ask the AI to analyze system data (ps aux, df -h, etc.) and provide recommendations.
File Management: Upload and download files directly from the chat.
Scripts and Backups: Securely execute predefined scripts.
Security: Restricted access for authorized users and a super-admin.
Internationalization: Support for multiple languages (defaulting to English and Spanish).
Notifications: Periodic status alerts and customizable reminders.
Proactive Security: Real-time alerts on log patterns and Fail2Ban integration to manage banned IPs.
Anti-Flood Protection: The bot ignores repeated commands within a short time frame to prevent spam and overload.
🚀 Architecture and Performance
This ensures that the bot never gets “stuck” and can continue to respond to multiple users and commands simultaneously, regardless of the background workload.

The bot has an anti-flood layer to prevent message saturation, either intentionally or accidentally.

Image and file repository. By default it will store any image or file that is added in the corresponding folders.

🔧 Prerequisites
Ensure you have the following components installed on the server where the bot will run.

System Dependencies:

sudo apt update
sudo apt install python3 python3-pip python3-venv git fortune nmap traceroute dnsutils whois
ansiweather: For weather lookups. It is installed separately; check its repository.
Git to clone the repository.

⚙️ Installation
Clone the repository:

git clone <REPOSITORY_URL>
cd <DIRECTORY_NAME>
Create and activate a virtual environment (recommended):

python3 -m venv venv
source venv/bin/activate
Install Python dependencies:

pip install python-telegram-bot[job-queue] google-generativeai psutil
🚀 Configuration
The configuration has been split to improve security.

1. Environment Variables (Secrets)
Create a .env file in the project root or export the variables directly.

# File: .env
TELEGRAM_TOKEN="12345:ABCDEFGHIJKLMN-OPQRSTUVWXYZ"
GEMINI_API_KEY="AIzaSy...YOUR_API_KEY_HERE"
2. Users File (users.json)
Create the users.json file. You will need your Telegram User ID to set yourself as the super-admin.

{
  "super_admin_id": 123456789,
  "authorized_users": [
    123456789,
    987654321
  ]
}
3. Configuration File (configbot.json)
Edit and renameconfigbot.json.example to configbot.json. Define paths to your scripts, the services you want to manage, servers to monitor, etc. Secrets are no longer stored here.

4. Sudo Permissions
The bot requires permissions to restart services or containers. This is critical for security. Edit the sudoers file with sudo visudo and add specific lines for the user that will run the bot. NEVER give passwordless sudo access to everything.

# /etc/sudoers
# Replace 'bot_user' with the actual username
bot_user ALL=(ALL) NOPASSWD: /usr/bin/systemctl start nginx, /usr/bin/systemctl stop nginx, /usr/bin/systemctl restart nginx, /usr/bin/docker restart my_container
5. Fail2Ban and Log Monitoring Configuration
Add the following sections to your configbot.json to enable these features:

fail2ban_jails: A list of jails where the unban command should search.
log_monitoring: Enables log watching, defines the check interval, and the files and patterns to look for.
▶️ Manual Execution
For testing or running directly in your terminal.

Make sure you have activated the virtual environment (source venv/bin/activate).
Export the environment variables if you are not using a system that loads them automatically.
export TELEGRAM_TOKEN="YOUR_TOKEN"
export GEMINI_API_KEY="YOUR_API_KEY"
Run the bot:
python3 bot_interactivo.py
⚙️ Running as a Service (Daemon) with systemd
To run the bot continuously in the background and have it start automatically on boot, you should set it up as a systemd service.

Step 1: Create the Environment File for the Service
The systemd service runs in an isolated environment and cannot see the variables you export in your terminal. Therefore, you must create a specific file for them.

Create a configuration directory for the bot:

sudo mkdir -p /etc/telegram-bot
Create the environment file with your secrets:

sudo nano /etc/telegram-bot/bot.env
Add the following content, without quotes:

# /etc/telegram-bot/bot.env
TELEGRAM_TOKEN=YOUR_TELEGRAM_TOKEN
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
Step 2: Secure the Environment File 🛡️
Ensure that only the user running the bot (and root) can read this file. Replace your_user with the username that will run the service.

sudo chown your_user:your_user /etc/telegram-bot/bot.env
sudo chmod 600 /etc/telegram-bot/bot.env
Step 3: Create the systemd Service File
This file defines how systemd should manage your bot.

Create the service file:

sudo nano /etc/systemd/system/telegram-bot.service
Paste the following content. Pay close attention to User, WorkingDirectory, and ExecStart and modify them according to your setup.

[Unit]
Description=Telegram SysAdmin Bot
# Ensures the network is available before starting
After=network.target

[Service]
# Replace 'your_user' with the user that will run the script
User=your_user
Group=your_user

# Replace with the absolute path to your bot's directory
WorkingDirectory=/home/your_user/telegram_bot

# --- Choose ONE of the following ExecStart lines ---

# OPTION A: If you use a VIRTUAL ENVIRONMENT (Recommended)
# Replace with the full path to the python executable in your venv
ExecStart=/home/your_user/telegram_bot/venv/bin/python3 /home/your_user/telegram_bot/bot_interactivo.py

# OPTION B: If you DO NOT use a virtual environment
# Uncomment this line and comment out the one above
# ExecStart=/usr/bin/python3 /home/your_user/telegram_bot/bot_interactivo.py

# Load environment variables from the file we created
EnvironmentFile=/etc/telegram-bot/bot.env

# Restart the service on failure
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
Step 4: Manage the Service
Once the .service file is saved, use the following commands to control your new daemon:

Reload systemd to detect the new service:
sudo systemctl daemon-reload
Enable the service to start on system boot:
sudo systemctl enable telegram-bot.service
Start the service now:
sudo systemctl start telegram-bot.service
Check the status to see if it's running and to check for errors:
sudo systemctl status telegram-bot.service
To stop the service: sudo systemctl stop telegram-bot.service
To restart it after a change: sudo systemctl restart telegram-bot.service
🌐 Localization
The bot uses gettext for translation.

To add a new language or update translations, edit the .po files in locales/<language_code>/LC_MESSAGES/.
After editing, compile the .po file into the .mo format:
msgfmt -o locales/es/LC_MESSAGES/base.mo locales/es/LC_MESSAGES/base.po
