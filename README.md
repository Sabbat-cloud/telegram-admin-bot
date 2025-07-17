# telegram-admin-bot
Friendly and reasonably simple telegram bot.

Aqui tienes un potente y versátil bot de Telegram diseñado para administradores de sistemas y desarrolladores. Permite monitorear, administrar y ejecutar tareas en tus servidores directamente desde la comodidad de tu chat de Telegram, de forma segura e interactiva.



✨ Características Principales:

Este bot convierte tu Telegram en una navaja suiza para la administración de sistemas.

📊 Monitoreo Integral:

Reporte de Estado Multiservidor: Verifica el estado de múltiples servidores a la vez (Ping, puertos abiertos, estado de certificados SSL).

Recursos del Sistema: Obtén en tiempo real el uso de CPU, RAM y Disco del servidor donde se aloja el bot.

Estado de Servicios: Comprueba el estado de servicios clave (systemd) como nginx, mysql, sshd, etc.

Alertas de Caducidad SSL: Te avisa cuando los certificados SSL de tus dominios están a punto de caducar.

⚙️ Administración Remota:

Ejecución de Scripts: Ejecuta de forma segura scripts shell o python predefinidos desde un menú. Ideal para backups, reinicios o tareas personalizadas.

Gestión de Tareas Cron: Visualiza las tareas programadas (crontab) del usuario del bot.

Gestión de Archivos:

Sube archivos o imágenes directamente al servidor arrastrándolos al chat.

Con la instalación se generan dos directorios . Por defecto `/images` y `/files` . Cualquier imagen que pongas en el bot se guardara en `images` y el resto de adjuntos en `files`. Puedes personalizar donde guardar los ficheros en la configuración 

Descarga archivos del servidor al chat con un simple comando.

🛠️ Herramientas de Red:

Accede a herramientas de diagnóstico esenciales desde menús interactivos o comandos directos:

`ping`

`traceroute`

`nmap` (escaneo de puertos y servicios)

🛡️ Seguridad y Usabilidad:

Control de Acceso: El bot solo responde a usuarios autorizados definidos en la configuración.

Jerarquía de Permisos: Incluye un rol de Super Administrador que es el único que puede añadir o eliminar a otros usuarios.

Gestión de Usuarios Dinámica: Añade o elimina usuarios autorizados con los comandos /adduser y /deluser sin necesidad de reiniciar el bot.

Interfaz Interactiva: Menús con botones en línea que facilitan la navegación y el uso sin tener que memorizar comandos.

Configuración Centralizada: Toda la configuración (tokens, usuarios, servidores, scripts) se gestiona desde un único archivo configbot.json.

🚀 Instalación y Configuración:

Sigue estos pasos para poner en marcha tu bot.

1. Prerrequisitos
Python 3.8 o superior.

Tener instaladas las herramientas de red que quieras usar (ej: traceroute, nmap).

`sudo apt update`
`sudo apt install traceroute nmap`

2. Clonar el Repositorio
`git clone https://github.com/Sabbat-cloud/telegram-admin-bot.git`
`cd telegram-admin-bot`

3. Instalar Dependencias
Se recomienda usar un entorno virtual.

`python -m venv venv`
`source venv/bin/activate`
`pip install -r requirements.txt`

`python-telegram-bot
psutil`

4. Configurar el Bot
Crea tu bot en Telegram: Habla con @BotFather para crear un nuevo bot. Guarda el token que te proporcione.

Obtén tu ID de Telegram: Habla con @userinfobot para saber tu ID de usuario numérico.

Configura configbot.json: Renombra configbot.example.json a configbot.json y edítalo con tu información.

5. Ejecutar el Bot
`python bot_interactivo.py`

Para mantenerlo corriendo en segundo plano, se recomienda usar systemd o tmux.

📖 Modo de Uso:

`/start`: Inicia el bot y muestra el menú principal.

`/help`: Muestra una lista detallada de todos los comandos y funcionalidades.

Navegación por menús: La mayoría de las funciones son accesibles a través de los botones interactivos.

Comandos de gestión (Solo Super Admin):

`/adduser <ID_de_usuario>`: Autoriza a un nuevo usuario.

`/deluser <ID_de_usuario>`: Revoca el acceso a un usuario.
