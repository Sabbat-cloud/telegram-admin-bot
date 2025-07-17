# telegram-admin-bot

Friendly and reasonably simple telegram bot.

Aquí tienes un potente y versátil bot de Telegram diseñado para administradores de sistemas y desarrolladores. Permite monitorear, administrar y ejecutar tareas en tus servidores directamente desde la comodidad de tu chat de Telegram, de forma segura e interactiva.

-----

### **Características Principales:**

Este bot convierte tu Telegram en una navaja suiza para la administración de sistemas.

-----

### **Novedades y Mejoras Recientes:**

  * **Monitorización Proactiva**: Configura umbrales para que el bot te notifique automáticamente sobre altos usos de CPU, disco o cuando hay actualizaciones de paquetes disponibles.
  * **Monitoreo Extendido**: Nuevos comandos para visualizar el uso de disco (`df -h`), listar procesos (`ps aux`) y obtener información detallada del sistema (`uname -a`, `lsb_release -a`).
  * **Gestión de Logs**: Accede a los logs de tu servidor (`tail`) y realiza búsquedas (`grep`) en ellos de forma segura, con una lista blanca configurable.
  * **Soporte Docker**: Lista contenedores, visualiza sus logs y reinícialos directamente desde Telegram.
  * **Más Herramientas de Red**: Incorporación de `dig` (consultas DNS) y `whois` (información de dominios).

-----

### **-.Monitorización Integral:**

  * **Reporte de Estado Multiservidor**: Verifica el estado de múltiples servidores a la vez (Ping, puertos abiertos, estado de certificados SSL).
  * **Recursos del Sistema**: Obtén en tiempo real el uso de CPU, RAM y Disco del servidor donde se aloja el bot.
  * **Uso de Disco Detallado**: Consulta el espacio en disco con el formato `df -h`.
  * **Procesos en Ejecución**: Lista todos los procesos activos en el servidor con `ps aux`.
  * **Información del Sistema**: Obtén detalles del kernel y la distribución Linux (`uname -a`, `lsb_release -a`).
  * **Estado de Servicios**: Comprueba el estado de servicios clave (systemd) como nginx, mysql, sshd, etc.
  * **Visualización y Búsqueda de Logs**: Accede a las últimas líneas de logs importantes o busca patrones específicos en ellos. **Configura una lista blanca de logs permitidos para seguridad.**
  * **Alertas de Caducidad SSL**: Te avisa cuando los certificados SSL de tus dominios están a punto de caducar.
  * **Monitoreo Proactivo (CPU, Disco, Actualizaciones)**: El bot puede configurarse para enviar notificaciones automáticas al Super Administrador si los umbrales de uso de CPU o disco son superados, o cuando hay actualizaciones de paquetes APT pendientes.

-----

### **Administración Remota:**

  * **Ejecución de Scripts**: Ejecuta de forma segura scripts shell o python predefinidos desde un menú. Ideal para backups, reinicios o tareas personalizadas.
  * **Gestión de Tareas Cron**: Visualiza las tareas programadas (`crontab`) del usuario del bot.
  * **Gestión de Contenedores Docker**: Lista contenedores activos, ve sus logs y reinicia contenedores permitidos.

-----

### **Gestión de Archivos:**

  * **Sube archivos o imágenes** directamente al servidor arrastrándolos al chat.
  * Con la instalación se generan dos directorios. Por defecto `/images` y `/files`. Cualquier imagen que subas al bot se guardará en `images` y el resto de adjuntos en `files`. Puedes personalizar dónde guardar los ficheros en la configuración.
  * **Descarga archivos** del servidor al chat con un simple comando.

-----

### **-. Herramientas de Red:**

Accede a herramientas de diagnóstico esenciales desde menús interactivos o comandos directos:

  * `ping`
  * `traceroute`
  * `nmap` (escaneo de puertos y servicios)
  * `dig` (consultas de registros DNS)
  * `whois` (información de registro de dominios)

-----

### **-. Seguridad y Usabilidad:**

  * **Control de Acceso**: El bot solo responde a usuarios autorizados definidos en la configuración.
  * **Jerarquía de Permisos**: Incluye un rol de Super Administrador que es el único que puede añadir o eliminar a otros usuarios.
  * **Gestión de Usuarios Dinámica**: Añade o elimina usuarios autorizados con los comandos `/adduser` y `/deluser` sin necesidad de reiniciar el bot.
  * **Listas Blancas Estrictas**: Los servicios, scripts, logs y contenedores Docker que el bot puede interactuar están definidos explícitamente en una lista blanca en el archivo de configuración, garantizando que solo se ejecuten acciones seguras y controladas.
  * **Interfaz Interactiva**: Menús con botones en línea que facilitan la navegación y el uso sin tener que memorizar comandos.
  * **Configuración Centralizada**: Toda la configuración (tokens, usuarios, servidores, scripts, logs, Docker, umbrales de monitoreo) se gestiona desde un único archivo `configbot.json`.

-----

### **-. Instalación y Configuración:**

Sigue estos pasos para poner en marcha tu bot.

#### 1\. Prerrequisitos

  * Python 3.8 o superior.
  * Tener instaladas las herramientas de red que quieras usar (ej: `traceroute`, `nmap`, `dig`, `whois`).
  * Tener `docker` instalado si planeas usar las funcionalidades de Docker.
  * **Para sistemas Debian/Ubuntu (apt):**
    ```bash
    sudo apt update
    sudo apt install traceroute nmap dnsutils whois
    ```
    (`dnsutils` incluye `dig`, `whois` es para `whois`).
  * **Permisos Sudo NOPASSWD**: El usuario bajo el cual se ejecuta el bot necesitará permisos `sudo NOPASSWD` para ciertos comandos (ej: `systemctl start/stop/restart`, `docker restart`, `apt update`). Edita tu archivo `/etc/sudoers` (usando `sudo visudo`) y añade líneas como las siguientes, ajustando `tu_usuario_bot` al usuario de tu sistema y los paths a los ejecutables correctos:
    ```
    tu_usuario_bot ALL=(ALL) NOPASSWD: /usr/bin/systemctl start *, /usr/bin/systemctl stop *, /usr/bin/systemctl restart *
    tu_usuario_bot ALL=(ALL) NOPASSWD: /usr/bin/docker restart *
    tu_usuario_bot ALL=(ALL) NOPASSWD: /usr/bin/apt update
    ```

#### 2\. Clonar el Repositorio

```bash
git clone https://github.com/Sabbat-cloud/telegram-admin-bot.git
cd telegram-admin-bot
```

#### 3\. Instalar Dependencias

Se recomienda usar un entorno virtual.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

```

#### 4\. Configurar el Bot

  * **Crea tu bot en Telegram**: Habla con `@BotFather` para crear un nuevo bot. Guarda el token que te proporcione.
  * **Obtén tu ID de Telegram**: Habla con `@userinfobot` para saber tu ID de usuario numérico.
  * **Configura `configbot.json`**: Renombra `configbot.example.json` a `configbot.json` (o edita el que ya tienes) y ábrelo. Edítalo con tu token, tu `super_admin_id`, y los `authorized_users`. Define tus `services_allowed`, `scripts_permitidos`, `python_scripts_permitidos`, `docker_containers_allowed` y `allowed_logs` (con sus rutas absolutas) según tus necesidades. Configura también los `monitoring_thresholds` para las alertas proactivas.

#### 5\. Ejecutar el Bot

```bash
python3 bot_interactivo.py
```

Para mantenerlo corriendo en segundo plano y asegurar el monitoreo proactivo (que se ejecuta en un hilo separado), se recomienda usar `systemd` o `tmux`.

-----

### **-. Modo de Uso:**

  * `/start`: Inicia el bot y muestra el menú principal.
  * `/help`: Muestra una lista detallada de todos los comandos y funcionalidades.

**Navegación por menús**: La mayoría de las funciones son accesibles a través de los botones interactivos:

  * **📊 Monitorización**: Accede a reportes de estado, uso de recursos (CPU, RAM, Disco), lista de procesos, información del sistema, logs y estado de servicios.
  * **⚙️ Administración**: Ejecuta scripts (shell/python) y consulta tareas cron.
  * **🛠️ Herramientas de Red**: Usa `ping`, `traceroute`, `nmap`, `dig` y `whois`.
  * **🐳 Gestión Docker**: Lista, visualiza logs y reinicia contenedores.
  * **📁 Gestión de Archivos**: Sube y descarga archivos.

**Comandos Directos Útiles:**

  * `/resources`: Muestra un resumen del uso de CPU, RAM y disco principal.
  * `/disk`: Muestra el uso de disco detallado con `df -h`.
  * `/processes`: Lista todos los procesos en ejecución con `ps aux`.
  * `/systeminfo`: Muestra información detallada del sistema operativo.
  * `/dig <dominio>`: Realiza una consulta DNS para el dominio especificado.
  * `/whois <dominio>`: Obtiene la información WHOIS de un dominio.
  * `/logs <nombre_log> [lineas]`: Muestra las últimas `N` líneas de un log configurado (ej: `/logs syslog 20`).
  * `/logs search <nombre_log> <patron>`: Busca un `patron` específico dentro de un log configurado (ej: `/logs auth 'failed password'`).
  * `/docker ps`: Lista los contenedores Docker activos.
  * `/docker logs <contenedor> [lineas]`: Muestra las últimas `N` líneas de los logs de un contenedor Docker permitido (ej: `/docker logs my_web_app 50`).
  * `/docker restart <contenedor>`: Reinicia un contenedor Docker permitido (ej: `/docker restart database_container`).
  * `/updates`: (Solo Super Admin) Fuerza una comprobación de actualizaciones de paquetes APT disponibles.
  * `/get <imagenes|ficheros> <nombre_archivo>`: Descarga un archivo del servidor al chat.

**Comandos de gestión (Solo Super Admin):**

  * `/adduser <ID_de_usuario>`: Autoriza a un nuevo usuario para usar el bot.
  * `/deluser <ID_de_usuario>`: Revoca el acceso a un usuario autorizado.

-----

### **Consejos de Seguridad:**

  * **¡Nunca compartas tu `telegram_token`\!**
  * Asegúrate de que los permisos `NOPASSWD` en `/etc/sudoers` sean lo más **específicos posible** para evitar ejecutar comandos arbitrarios con `sudo`.
  * Mantén las listas `scripts_permitidos`, `python_scripts_permitidos`, `allowed_logs` y `docker_containers_allowed` lo más restringidas posible a lo estrictamente necesario.
  * Considera ejecutar el bot bajo un usuario de sistema con permisos limitados.

-----
