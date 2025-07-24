# Telegram Admin & Monitoring Bot

Este es un potente y versátil bot de Telegram diseñado para la administración, monitorización y gestión de servidores Linux. Ofrece una interfaz interactiva y segura para realizar una amplia variedad de tareas directamente desde tu chat de Telegram.

This is a powerful and versatile Telegram bot designed for the administration, monitoring, and management of Linux servers. It provides a secure and interactive interface to perform a wide variety of tasks directly from your Telegram chat.

---

## 🇪🇸 Español

### ✨ Características

* **Monitorización del Sistema:** Obtén reportes en tiempo real de CPU, RAM, disco, procesos y más.
* **Gestión de Servicios y Docker:** Revisa el estado de servicios (`systemctl`) y gestiona tus contenedores Docker (listar, ver logs, reiniciar).
* **Ejecución Remota:** Ejecuta de forma segura scripts Shell y Python pre-autorizados en tu servidor.
* **Herramientas de Red:** Lanza `ping`, `traceroute`, `nmap`, `dig` y `whois` desde el bot.
* **Gestión de Archivos:** Sube y descarga archivos desde y hacia el servidor., solo tienes que subir una foto o fichero y se guardara automáticamente en las carpetas designadas.
* **Integración con IA:** Realiza consultas a la API de Gemini de Google (modelos Flash y Pro).
* **Control de Acceso:** Sistema de usuarios seguro con un Super Administrador que gestiona los permisos.
* **Multi-idioma:** Interfaz disponible en Español e Inglés.
* **Utilidades:** Incluye recordatorios, consulta del tiempo y galletas de la fortuna (`fortune`).

### 🔧 Instalación

**1. Prerrequisitos:**
* Python 3.8 o superior.
* `pip` (gestor de paquetes de Python).
* Las siguientes herramientas de línea de comandos instaladas en el servidor:
    ```bash
    sudo apt-get update
    sudo apt-get install nmap dnsutils whois fortune ansiweather
    ```

**2. Clonar el Repositorio:**
```bash
git clone <URL_DEL_REPOSITORIO>
cd <NOMBRE_DEL_DIRECTORIO>
```

**3. Instalar Dependencias de Python:**
```bash
pip install -r requirements.txt
```

**4. Configurar el Bot:**
* Busca el archivo `configbot.json.example` y **renómbralo** a `configbot.json`.
    ```bash
    mv configbot.json.example configbot.json
    ```
* Edita el nuevo `configbot.json` y rellena todos los campos con tus datos reales:
    * **`telegram.token`**: El token de tu bot, obtenido de @BotFather.
    * **`telegram.super_admin_id`**: Tu ID de usuario de Telegram.
    * **`gemini_api.api_key`**: Tu clave de la API de Google AI Studio.
    * Configura el resto de rutas, servicios y servidores según tus necesidades.

**5. Ejecutar el Bot:**
```bash
python3 bot_interactivo.py
```
Se recomienda ejecutar el bot dentro de un servicio `systemd` o una sesión `screen`/`tmux` para que se mantenga en funcionamiento de forma persistente.

---

## 🇬🇧 English

### ✨ Features

* **System Monitoring:** Get real-time reports on CPU, RAM, disk usage, processes, and more.
* **Service & Docker Management:** Check the status of services (`systemctl`) and manage your Docker containers (list, view logs, restart).
* **Remote Execution:** Securely run pre-authorized Shell and Python scripts on your server.
* **Network Tools:** Launch `ping`, `traceroute`, `nmap`, `dig`, and `whois` from the bot.
* **File Management:** Upload and download files to and from the server. Just put a photo or file and it will automatically save it in the designated folders.
* **AI Integration:** Make queries to Google's Gemini API (Flash and Pro models).
* **Access Control:** Secure user system with a Super Admin who manages permissions.
* **Multi-language:** Interface available in English and Spanish.
* **Utilities:** Includes reminders, weather forecasts, and fortune cookies (`fortune`).

### 🔧 Installation

**1. Prerequisites:**
* Python 3.8 or higher.
* `pip` (Python package installer).
* The following command-line tools installed on the server:
    ```bash
    sudo apt-get update
    sudo apt-get install nmap dnsutils whois fortune ansiweather
    ```

**2. Clone the Repository:**
```bash
git clone <REPOSITORY_URL>
cd <DIRECTORY_NAME>
```

**3. Install Python Dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configure the Bot:**
* Find the `configbot.json.example` file and **rename it** to `configbot.json`.
    ```bash
    mv configbot.json.example configbot.json
    ```
* Edit the new `configbot.json` and fill in all the fields with your actual data:
    * **`telegram.token`**: Your bot's token, obtained from @BotFather.
    * **`telegram.super_admin_id`**: Your personal Telegram User ID.
    * **`gemini_api.api_key`**: Your API key from Google AI Studio.
    * Configure the rest of the paths, services, and servers to fit your needs.

**5. Run the Bot:**
```bash
python3 bot_interactivo.py
```
It is recommended to run the bot inside a `systemd` service or a `screen`/`tmux` session to keep it running persistently.
