# telegram-admin-bot
Friendly and reasonably simple telegram bot.

# Bot de Telegram para Administración de Sistemas

Un bot de Telegram multifuncional escrito en Python para monitorizar, administrar y realizar diagnósticos de red en sistemas Linux de forma remota y segura.

## 🚀 Características

-   **Monitorización de Sistemas**: Obtén reportes de estado de múltiples servidores, incluyendo ping, puertos abiertos y validez de certificados SSL.
-   **Recursos del Host**: Revisa el uso de CPU, RAM y Disco del sistema donde corre el bot.
-   **Administración de Scripts**: Ejecuta scripts de Shell y Python pre-autorizados de forma segura desde el menú del bot.
-   **Herramientas de Red**: Lanza `ping`, `traceroute` y `nmap` contra cualquier host, directamente desde Telegram.
-   **Gestión de Archivos**: Sube y descarga ficheros a/desde el servidor.
-   **Seguridad**: El acceso está restringido a una lista de IDs de usuario autorizados.

## ⚙️ Requisitos Previos

-   Python 3.8+
-   `pip` y `venv`
-   `git` (para la instalación)
-   Herramientas de red: `ping`, `traceroute`, `nmap` (`sudo apt install traceroute nmap`)

## 🔧 Instalación

1.  **Clona el repositorio:**
    ```bash
    git clone [https://github.com/tu-usuario/telegram-admin-bot.git](https://github.com/tu-usuario/telegram-admin-bot.git)
    cd telegram-admin-bot
    ```

2.  **Crea tu fichero de configuración:**
    Copia la plantilla y edítala con tus datos (token del bot, tu ID de usuario, etc.).
    ```bash
    cp config.json.template config.json
    nano config.json
    ```

3.  **Crea un entorno virtual e instala las dependencias:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

4.  **Ejecuta el bot:**
    ```bash
    python3 bot.py
    ```

Para mantenerlo corriendo en segundo plano, se recomienda usar un servicio de `systemd` o una herramienta como `supervisor` o `tmux`.

## 📜 Licencia

Este proyecto está bajo la Licencia MIT. Ver el fichero `LICENSE` para más detalles.
