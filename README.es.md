# SysAdmin Telegram Bot

Un potente y modular bot de Telegram para la administración y monitorización de servidores, escrito en Python. Integra herramientas de red, gestión de Docker, seguridad con Fail2Ban y capacidades de IA a través de la API de Gemini de Google.


## ✨ Características Principales

Este bot está diseñado para ser una navaja suiza para administradores de sistemas, ofreciendo una amplia gama de funcionalidades accesibles desde cualquier lugar a través de Telegram.

### **📊 Monitorización y Estado**
- **Menú Interactivo**: Interfaz limpia basada en botones para una fácil navegación.
- **Estado General**: Chequea el estado (ping, puertos, SSL) de múltiples servidores definidos en la configuración.
- **Recursos del Sistema**: Obtiene informes en tiempo real de CPU, carga media, RAM y uso de disco.
- **Gestión de Servicios**: Comprueba, inicia, detiene y reinicia servicios del sistema (`systemd`).
- **Visualización de Logs**: Lee las últimas líneas de logs pre-configurados y busca patrones dentro de ellos.

### **🛠️ Administración y Herramientas**
- **Ejecución de Scripts**: Ejecuta de forma segura scripts `shell` (.sh) y `python` (.py) pre-autorizados.
- **Gestión de Docker**: Lista contenedores activos, visualiza sus logs y los reinicia.
- **Herramientas de Red**: Ejecuta `ping`, `traceroute`, `nmap`, `dig` y `whois` sobre objetivos definidos.
- **Gestión de Backups**: Lanza scripts de respaldo directamente desde el bot.
- **Visualización de Cron**: Muestra las tareas programadas (`crontab`) del usuario del bot.

### **🛡️ Seguridad**
- **Control de Acceso**: Sistema de autorización multinivel con un `super_admin_id` y una lista de `authorized_users`.
- **Integración con Fail2Ban**: Comprueba el estado de las jaulas y permite desbloquear direcciones IP.
- **Sellado de Scripts**: Un mecanismo de seguridad que almacena y verifica el hash `SHA256` de cada script antes de ejecutarlo, impidiendo la ejecución de código modificado sin autorización.
- **Validación de Entradas**: Sanea y valida todas las entradas del usuario para prevenir ataques (ej. path traversal, inyección de comandos).

### **🤖 Integración con IA (Google Gemini)**
- **/ask**: Realiza preguntas de propósito general a un modelo rápido (Gemini Flash).
- **/askpro**: (Solo Super Admin) Realiza consultas complejas a un modelo más avanzado (Gemini Pro).
- **/analyze**: Pide a la IA que analice datos del sistema (`status`, `resources`, `disk`) y ofrezca un diagnóstico o recomendaciones.

### **⚙️ Utilidades y Personalización**
- **Gestión de Archivos**: Sube archivos y fotos al servidor y descarga archivos desde directorios pre-configurados.
- **Multilenguaje**: Soporte para múltiples idiomas (español e inglés por defecto) gracias a `gettext`.
- **Recordatorios**: Establece recordatorios (`/remind "texto" in 1d 2h`) con un sistema de cola de trabajos.
- **Persistencia**: Guarda el idioma seleccionado por el usuario y otros datos entre reinicios del bot.
- **Otras Utilidades**: Incluye comandos divertidos como `/fortune` y una consulta de tiempo.

---

## 🚀 Instalación y Puesta en Marcha

Sigue estos pasos para configurar y lanzar tu propio bot.

### **1. Prerrequisitos**
- Python 3.8 o superior.
- Un token de bot de Telegram (obtenido de [@BotFather](https://t.me/BotFather)).
- (Opcional) Una API Key de Google Gemini.

### **2. Clonar y Preparar el Entorno**
```bash
# Clona el repositorio
git clone https://github.com/Sabbat-cloud/telegram-admin-bot
cd telegram-admin-bot

# Crea y activa un entorno virtual
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instala las dependencias
pip install -r requirements.txt
```

### **3. Configuración de Ficheros**

El bot utiliza una configuración centralizada y segura.

**a) Secretos (`/etc/telegram-bot/bot.env`)**

Crea un fichero en una ruta segura (fuera del repositorio) para almacenar tus credenciales.

```ini
# /etc/telegram-bot/bot.env
TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
GEMINI_API_KEY="TuApiKeyDeGeminiOpcional"
```

**b) Usuarios (`users.json`)**

Crea este fichero en el directorio principal del bot para definir quién puede usarlo.

```json
{
  "super_admin_id": 123456789,
  "authorized_users": [
    123456789,
    987654321
  ]
}
```
> **Nota**: Puedes obtener tu ID de Telegram hablando con bots como [@userinfobot](https://t.me/userinfobot).

**c) Configuración Principal (`configbot.json`)**

Este es el corazón de la configuración. Adapta los scripts, servicios, servidores y otras opciones a tus necesidades. El fichero de ejemplo es un buen punto de partida.

### **4. Preparar Scripts y "Sellarlos"**

Por seguridad, el bot solo ejecutará scripts que hayas "sellado" previamente.

1.  Coloca tus scripts `.sh` o `.py` en las rutas que has definido en `configbot.json`.
2.  Ejecuta el script de sellado para calcular y guardar sus hashes:
    ```bash
    python seal_scripts.py
    ```
    Este proceso actualizará `configbot.json` con los hashes `sha256` de tus scripts. **Debes repetir este paso cada vez que modifiques un script.**

### **5. Configurar Idiomas (Localization)**

Si has añadido o modificado traducciones en los ficheros `.po` dentro del directorio `locales`:
```bash
# Compila los ficheros de idioma
pybabel compile -d locales
```

### **6. Iniciar el Bot**
```bash
python bot_interactivo.py
```
¡Tu bot ya está en funcionamiento! Puedes hablar con él en Telegram. Para mantenerlo activo de forma permanente, considera usar `systemd` o `screen`.

---

## 🔐 Consideraciones de Seguridad

- **Mínimo Privilegio**: Ejecuta el bot con un usuario del sistema que no sea `root` y que tenga los permisos estrictamente necesarios.
- **Permisos `sudo`**: Si algunos comandos requieren `sudo` (como la gestión de servicios), configura `sudoers` para permitir que el usuario del bot ejecute *solo* esos comandos específicos sin contraseña.
- **Ruta de Secretos**: Asegúrate de que el fichero `.env` esté en una ubicación segura y con permisos de lectura solo para el usuario del bot.
- **Sellado de Scripts**: No subestimes la importancia del sellado. Es tu principal defensa contra la ejecución de código no autorizado si alguien logra acceder a la carpeta de scripts.

---

## License

Este proyecto está bajo la Licencia MIT.
