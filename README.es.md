# Bot de Administración de Servidores para Telegram

[**Español**] | [English](README.md)

Un bot de Telegram potente y seguro, escrito en Python, diseñado para monitorizar y administrar servidores Linux directamente desde tu móvil. Integra herramientas de sistema, utilidades de red, gestión de servicios, Docker, Fail2Ban y la API de Gemini de Google para análisis inteligente.

---

## ✨ Características

- **💻 Monitorización del Sistema**:
  - Estado general de servicios y puertos (`/status`).
  - Uso de recursos en tiempo real (CPU, RAM, Carga Media) (`/resources`).
  - Uso de disco (`/disk`).
  - Listado de procesos (`/processes`).
  - Información del sistema y distribución (`/systeminfo`).

- **🛡️ Seguridad y Administración**:
  - **Ejecución Segura de Scripts**: Ejecuta scripts `.sh` y `.py` pre-configurados, con verificación de integridad mediante hash SHA256 para prevenir ejecuciones no autorizadas.
  - **Gestión de Servicios**: Inicia, para, reinicia y comprueba el estado de servicios del sistema (ej. `nginx`, `mysql`) con `systemctl`.
  - **Gestión de Fail2Ban**: Comprueba el estado de las jaulas y desbloquea IPs directamente desde el bot.
  - **Gestión de Tareas Cron**: Visualiza las tareas programadas.
  - **Gestión de Usuarios**: Sistema de autorización con un super administrador y usuarios autorizados.

- **🐳 Gestión de Docker**:
  - Lista los contenedores activos (`docker ps`).
  - Reinicia contenedores permitidos.
  - Visualiza los logs de un contenedor.

- **🌐 Herramientas de Red**:
  - `ping`, `traceroute`, `nmap -A`, `dig`, `whois`.

- **🤖 Integración con IA (Google Gemini)**:
  - `/ask`: Realiza consultas rápidas al modelo Gemini Flash.
  - `/askpro`: Realiza consultas complejas al modelo Gemini Pro (solo super admin).
  - `/analyze`: Pide a la IA que analice los datos de monitorización y ofrezca recomendaciones.

- **📁 Gestión de Archivos**:
  - Sube archivos e imágenes directamente al servidor a través del chat.
  - Descarga archivos del servidor al chat con el comando `/get`.

- **🔔 Alertas y Utilidades**:
  - Monitorización periódica de logs con alertas por patrones.
  - Alertas por umbrales de CPU y disco.
  - Sistema de recordatorios (`/remind`).
  - Soporte multi-idioma (Español e Inglés).

---

## 🚀 Instalación y Puesta en Marcha

#### 1. Requisitos Previos
- Un servidor Linux (probado en Debian/Ubuntu).
- Python 3.10 o superior.
- Herramientas de sistema instaladas: `ping`, `traceroute`, `nmap`, `dig`, `whois`, `fortune`, `ansiweather`.
  ```bash
  sudo apt update
  sudo apt install dnsutils nmap whois fortune ansiweather
  ```

#### 2. Clonar y Preparar el Entorno
```bash
# Clona el repositorio (o copia los ficheros)
git clone [https://tu-repositorio.git](https://tu-repositorio.git)
cd tu-repositorio

# (Opcional pero recomendado) Crear un entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependencias de Python
pip install -r requirements.txt
```

#### 3. Configuración de Ficheros
Crea la siguiente estructura de directorios para los secretos:
```bash
sudo mkdir -p /etc/telegram-bot
sudo chown $USER:$USER /etc/telegram-bot
```

- **`bot.env`** (Fichero de secretos): Crea este fichero en `/etc/telegram-bot/bot.env`.
  ```env
  # Token de tu bot de Telegram obtenido de @BotFather
  TELEGRAM_TOKEN=12345:ABC...

  # API Key de Google Gemini (opcional, para funciones de IA)
  GEMINI_API_KEY=AIzaSy...
  ```

- **`users.json`**: Coloca este fichero en el mismo directorio que el bot. Contiene los IDs de los usuarios autorizados.
  ```json
  {
    "super_admin_id": 123456789,
    "authorized_users": [
      123456789,
      987654321
    ]
  }
  ```

- **`configbot.json`**: Este es el fichero de configuración principal. Revísalo y ajústalo a tus necesidades (rutas de scripts, servicios permitidos, etc.).

#### 4. Configuración de Seguridad

- **Permisos de `sudo`**: Para que el bot pueda reiniciar servicios y usar Docker sin contraseña, añade una regla con `sudo visudo`:
  ```sudoers
  # Reemplaza 'tu_usuario' por el usuario que ejecutará el bot
  tu_usuario ALL=(root) NOPASSWD: /bin/systemctl start *, /bin/systemctl stop *, /bin/systemctl restart *, /bin/docker restart *
  ```

- **Sellar los Scripts**: Por seguridad, el bot solo ejecutará scripts cuyo hash coincida con el guardado en `configbot.json`. Para generar o actualizar estos hashes, ejecuta:
  ```bash
  python3 seal_scripts.py
  ```
  La primera vez que configures tus scripts, o cada vez que los modifiques, debes ejecutar este comando.

#### 5. Ejecutar el Bot
Puedes ejecutarlo directamente o, preferiblemente, como un servicio de `systemd`.
```bash
# Ejecución directa
python3 bot_interactivo.py
```

---

## 🛠️ Uso
- Envía `/start` al bot para ver el menú principal.
- La mayoría de las funciones son accesibles a través de los botones del menú.
- Consulta `/help` para ver una lista completa de comandos de texto disponibles.

---

## 📄 Licencia
Este proyecto está bajo la Licencia MIT.
