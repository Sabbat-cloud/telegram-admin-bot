#Bot interactivo telegram Version 1.4
#Por Óscar Giménez Blasco
#
import json
import socket
import subprocess
import platform
import re
import datetime
import logging
import os
import sys
import ssl
import psutil
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackQueryHandler
from telegram.helpers import escape_markdown

# --- CONFIGURACIÓN DE LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='monitor.log',
    filemode='a'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

CONFIG_FILE = 'configbot.json'

# --- DECORADORES Y FUNCIONES DE UTILIDAD ---
def authorized_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        config = cargar_configuracion()
        authorized_users = config.get("telegram", {}).get("authorized_users", [])
        if user_id not in authorized_users:
            logging.warning(f"Acceso no autorizado denegado para el usuario con ID: {user_id}")
            if update.callback_query:
                await update.callback_query.answer("❌ No tienes permiso.", show_alert=True)
            else:
                await update.message.reply_text("❌ No tienes permiso para usar este bot.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# NUEVO DECORADOR PARA SUPER ADMIN
def super_admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        config = cargar_configuracion()
        super_admin_id = config.get("telegram", {}).get("super_admin_id")
        if user_id != super_admin_id:
            logging.warning(f"Intento de ejecución de comando de super admin por usuario no autorizado: {user_id}")
            await update.message.reply_text("⛔ Este comando solo puede ser usado por el super administrador.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# CARGA Y GUARDADO DEL FICHERO JSON
def cargar_configuracion():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: El archivo de configuración '{CONFIG_FILE}' no se encontró.")
        sys.exit()
    except json.JSONDecodeError:
        logging.error(f"Error: El archivo de configuración '{CONFIG_FILE}' tiene un formato JSON inválido.")
        sys.exit()

# NUEVA FUNCIÓN PARA GUARDAR LA CONFIGURACIÓN
def guardar_configuracion(config_data):
    """Escribe el diccionario de configuración de nuevo en el archivo JSON."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error al guardar la configuración en '{CONFIG_FILE}': {e}")
        return False

# --- MÓDULOS DE VERIFICACIÓN (Lógica principal) ---
def check_ping(host):
    param = '-n 1' if platform.system().lower() == 'windows' else '-c 1'
    command = ['ping', param, host]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        return "✅ Ping: **Accesible**" if result.returncode == 0 else "❌ Ping: **INACCESIBLE**"
    except subprocess.TimeoutExpired:
        return "❌ Ping: **Timeout**"

def check_port(host, port_name, port_num):
    try:
        with socket.create_connection((host, port_num), timeout=3):
            return f"✅ Puerto {port_name} ({port_num}): **Abierto**"
    except (socket.timeout, ConnectionRefusedError, OSError):
        return f"❌ Puerto {port_name} ({port_num}): **Cerrado**"

def check_ssl_expiry(host, port, days_warning):
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                expiry_date = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                days_left = (expiry_date - datetime.datetime.now()).days
                if days_left > days_warning:
                    return f"✅ Cert. SSL: Expira en **{days_left} días**"
                return f"🔥 Cert. SSL: Expira en **{days_left} días** (Aviso a los {days_warning})"
    except Exception as e:
        logging.warning(f"Error SSL para {host}: {e}")
        return "❌ Cert. SSL: **No se pudo verificar**"


# --- LÓGICA DE COMANDOS (Aplicada salida para menus) ---
def get_resources_text():
    """Genera el texto del reporte de recursos del sistema."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        try:
            cpu_load = psutil.getloadavg()
            load_avg_text = f"Carga media (1, 5, 15 min): `{cpu_load[0]:.2f}`, `{cpu_load[1]:.2f}`, `{cpu_load[2]:.2f}`\n"
        except AttributeError:
            load_avg_text = ""
        ram = psutil.virtual_memory()
        ram_total = f"{ram.total / (1024**3):.2f} GB"
        ram_used = f"{ram.used / (1024**3):.2f} GB"
        ram_percent = ram.percent
        disk = psutil.disk_usage('/')
        disk_total = f"{disk.total / (1024**3):.2f} GB"
        disk_used = f"{disk.used / (1024**3):.2f} GB"
        disk_percent = disk.percent
        return (
            f"💻 **Reporte de Recursos del Sistema**\n\n"
            f"--- **CPU** ---\n"
            f"Uso actual: `{cpu_percent}%`\n"
            f"{load_avg_text}\n"
            f"--- **Memoria (RAM)** ---\n"
            f"Uso: `{ram_used}` de `{ram_total}` (*{ram_percent}%*)\n\n"
            f"--- **Disco Principal (/)** ---\n"
            f"Uso: `{disk_used}` de `{disk_total}` (*{disk_percent}%*)"
        )
    except Exception as e:
        logging.error(f"Error inesperado en get_resources_text con psutil: {e}")
        return f"❌ **Error inesperado al obtener recursos:** {e}"

def get_status_report_text():
    """Genera el texto del reporte de estado completo."""
    config = cargar_configuracion()
    reporte_data = {}
    for servidor in config.get("servidores", []):
        nombre_servidor = servidor.get("nombre", "Servidor sin nombre")
        host = servidor.get("host")
        if not host: continue
        reporte_data[nombre_servidor] = []
        if "ping" in servidor.get("chequeos", {}):
            reporte_data[nombre_servidor].append(check_ping(host))
        if "puertos" in servidor.get("chequeos", {}):
            for nombre_puerto, num_puerto in servidor["chequeos"]["puertos"].items():
                reporte_data[nombre_servidor].append(check_port(host, nombre_puerto, num_puerto))
        if "certificado_ssl" in servidor.get("chequeos", {}):
            params = servidor["chequeos"]["certificado_ssl"]
            reporte_data[nombre_servidor].append(check_ssl_expiry(host, params.get("puerto", 443), params.get("dias_aviso", 30)))

    nombre_maquina_local = platform.node()
    encabezado = f"📋 **Reporte de Estado (desde {nombre_maquina_local})**\n"
    lineas_reporte = [encabezado]
    for servidor, checks in reporte_data.items():
        lineas_reporte.append(f"\n--- **{servidor}** ---")
        lineas_reporte.extend(checks)
    fecha = f"\n_{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
    lineas_reporte.append(fecha)
    return "\n".join(lineas_reporte)

# --- FUNCIONES DE RED ---
def do_ping(host: str) -> str:
    """Ejecuta un ping con 4 paquetes."""
    try:
        param = '-n 4' if platform.system().lower() == 'windows' else '-c 4'
        proc = subprocess.run(['ping', param, host], capture_output=True, text=True, timeout=20)
        output = proc.stdout or proc.stderr
        return f"📡 **Resultado de Ping a `{host}`:**\n```\n{output}\n```"
    except FileNotFoundError:
        return "❌ Error: El comando `ping` no se encuentra."
    except subprocess.TimeoutExpired:
        return f"❌ Error: Timeout (20s) haciendo ping a `{host}`."
    except Exception as e:
        return f"❌ Error inesperado: {e}"

def do_traceroute(host: str) -> str:
    """Ejecuta un traceroute."""
    try:
        command = ['traceroute', '-w', '2', host]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=60)
        output = proc.stdout or proc.stderr
        return f"🗺️ **Resultado de Traceroute a `{host}`:**\n```\n{output}\n```"
    except FileNotFoundError:
        return "❌ Error: El comando `traceroute` no se encuentra. ¿Está instalado?"
    except subprocess.TimeoutExpired:
        return f"❌ Error: Timeout (60s) durante el traceroute a `{host}`."
    except Exception as e:
        return f"❌ Error inesperado: {e}"

def do_nmap(host: str) -> str:
    """Ejecuta un escaneo nmap -A."""
    try:
        command = ['nmap', '-A', host]
        proc = subprocess.run(command, capture_output=True, text=True, timeout=600)
        output = proc.stdout or proc.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n\n... (salida truncada)"
        return f"🔬 **Resultado de Nmap -A a `{host}`:**\n```\n{output}\n```"
    except FileNotFoundError:
        return "❌ Error: El comando `nmap` no se encuentra. ¿Está instalado?"
    except subprocess.TimeoutExpired:
        return f"❌ Error: Timeout (10 min) durante el escaneo nmap a `{host}`."
    except Exception as e:
        return f"❌ Error inesperado: {e}"


# --- MENÚS ---
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Monitorización", callback_data='menu:monitor')],
        [InlineKeyboardButton("⚙️ Administración", callback_data='menu:admin')],
        [InlineKeyboardButton("🛠️ Herramientas de Red", callback_data='menu:network_tools')],
        [InlineKeyboardButton("📁 Gestión de Archivos", callback_data='menu:files')],
        [InlineKeyboardButton("🔄 Actualizar", callback_data='refresh_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def monitor_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Sistemas (Status General)", callback_data='monitor:status_all')],
        [InlineKeyboardButton("Recursos Locales (CPU/RAM)", callback_data='monitor:resources')],
        [InlineKeyboardButton("Estado de un Servicio", callback_data='menu:services')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='menu:main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("▶️ Ejecutar Script Shell", callback_data='menu:run_script_shell')],
        [InlineKeyboardButton("🐍 Ejecutar Script Python", callback_data='menu:run_script_python')],
        [InlineKeyboardButton("🗓️ Ver Tareas Cron", callback_data='admin:check_cron')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='menu:main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def files_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🖼️ Listar Imágenes", callback_data='files:list_imagenes')],
        [InlineKeyboardButton("📄 Listar Ficheros", callback_data='files:list_ficheros')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='menu:main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def network_tools_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📡 Ping", callback_data='network:select_ping')],
        [InlineKeyboardButton("🗺️ Traceroute", callback_data='network:select_traceroute')],
        [InlineKeyboardButton("🔬 Escaneo Nmap (-A)", callback_data='network:select_nmap')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='menu:main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def dynamic_host_keyboard(action: str):
    config = cargar_configuracion()
    hosts = config.get("servidores", [])
    keyboard = []
    for server in hosts:
        host_name = server.get("host")
        display_name = server.get("nombre")
        if host_name and display_name:
            keyboard.append([InlineKeyboardButton(f"🎯 {display_name} ({host_name})", callback_data=f"run:{action}:{host_name}")])
    keyboard.append([InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data='menu:network_tools')])
    return InlineKeyboardMarkup(keyboard)


def dynamic_script_keyboard(script_type):
    config = cargar_configuracion()
    key = "scripts_permitidos" if script_type == 'shell' else "python_scripts_permitidos"
    callback_prefix = "run:shell:" if script_type == 'shell' else "run:python:"
    scripts = config.get(key, {})
    keyboard = []
    for name in scripts:
        keyboard.append([InlineKeyboardButton(f"Ejecutar '{name}'", callback_data=f"{callback_prefix}{name}")])
    keyboard.append([InlineKeyboardButton("⬅️ Volver a Admin", callback_data='menu:admin')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_services_keyboard():
    config = cargar_configuracion()
    services = config.get("servicios_permitidos", [])
    keyboard = []
    for service in services:
        keyboard.append([InlineKeyboardButton(f"Estado de '{service}'", callback_data=f"service:{service}")])
    keyboard.append([InlineKeyboardButton("⬅️ Volver a Monitor", callback_data='menu:monitor')])
    return InlineKeyboardMarkup(keyboard)

# --- COMANDOS Y MANEJADOR DE MENÚS ---
@authorized_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"¡Hola {user.first_name}! 👋\n\n"
        "Selecciona una opción del menú para empezar. Usa /help para ver todos los comandos.",
        reply_markup=main_menu_keyboard()
    )

@authorized_only
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Navegación entre menús
    if data == 'menu:main':
        await query.edit_message_text(text="Menú Principal", reply_markup=main_menu_keyboard())
    elif data == 'menu:monitor':
        await query.edit_message_text(text="Menú de Monitorización", reply_markup=monitor_menu_keyboard())
    elif data == 'menu:admin':
        await query.edit_message_text(text="Menú de Administración", reply_markup=admin_menu_keyboard())
    elif data == 'menu:files':
        await query.edit_message_text(text="Menú de Gestión de Archivos\n\nRecuerda que para subir, solo tienes que enviar el archivo o la foto al chat.", reply_markup=files_menu_keyboard())
    elif data == 'menu:network_tools':
        await query.edit_message_text(text="🛠️ Herramientas de Red\n\nElige una herramienta del menú o escribe el comando directamente (ej: `/nmap 8.8.8.8`).", reply_markup=network_tools_menu_keyboard())
    elif data == 'refresh_main':
        await query.edit_message_text(text=f"Menú actualizado a las {datetime.datetime.now().strftime('%H:%M:%S')}", reply_markup=main_menu_keyboard())

    # Selección de objetivos para herramientas de red
    elif data == 'network:select_ping':
        texto = "📡 **Ping**\n\nSelecciona un objetivo de la lista o escribe el comando directamente.\n*Ejemplo: `/ping 8.8.8.8`*"
        await query.edit_message_text(texto, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('ping'))
    elif data == 'network:select_traceroute':
        texto = "🗺️ **Traceroute**\n\nSelecciona un objetivo de la lista o escribe el comando directamente.\n*Ejemplo: `/traceroute google.com`*"
        await query.edit_message_text(texto, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('traceroute'))
    elif data == 'network:select_nmap':
        texto = "🔬 **Escaneo Nmap**\n\nSelecciona un objetivo de la lista o escribe el comando directamente.\n*Ejemplo: `/nmap sabbat.cloud`*"
        await query.edit_message_text(texto, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('nmap'))

    # Ejecución de herramientas de red
    elif data.startswith('run:ping:'):
        host = data.split(':', 2)[2]
        await query.edit_message_text(f"📡 Haciendo ping a `{host}`...", parse_mode='Markdown')
        result = do_ping(host)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('ping'))
    elif data.startswith('run:traceroute:'):
        host = data.split(':', 2)[2]
        await query.edit_message_text(f"🗺️ Ejecutando traceroute a `{host}`...", parse_mode='Markdown')
        result = do_traceroute(host)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('traceroute'))
    elif data.startswith('run:nmap:'):
        host = data.split(':', 2)[2]
        await query.edit_message_text(f"🔬 Ejecutando escaneo Nmap a `{host}`... (esto puede tardar varios minutos)", parse_mode='Markdown')
        result = do_nmap(host)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('nmap'))

    # Acciones de Monitorización
    elif data == 'monitor:status_all':
        await query.edit_message_text("🔍 Obteniendo estado de todos los servidores...", parse_mode='Markdown')
        reporte = get_status_report_text()
        await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard())
    elif data == 'monitor:resources':
        await query.edit_message_text("📊 Recopilando información de los recursos del sistema...", parse_mode='Markdown')
        reporte = get_resources_text()
        await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard())
    elif data == 'menu:services':
        await query.edit_message_text("Selecciona el servicio para ver su estado:", reply_markup=dynamic_services_keyboard())

    # Acciones de Administración
    elif data == 'menu:run_script_shell':
        await query.edit_message_text("Selecciona el script de Shell a ejecutar:", reply_markup=dynamic_script_keyboard('shell'))
    elif data == 'menu:run_script_python':
        await query.edit_message_text("Selecciona el script de Python a ejecutar:", reply_markup=dynamic_script_keyboard('python'))
    elif data == 'admin:check_cron':
        try:
            proceso = subprocess.run('crontab -l', shell=True, capture_output=True, text=True, timeout=10)
            if proceso.stderr and "no crontab for" in proceso.stderr:
                salida = "ℹ️ No hay tareas de cron configuradas para el usuario actual."
            elif proceso.returncode != 0:
                salida = f"❌ **Error al leer crontab:**\n`{proceso.stderr}`"
            else:
                salida = f"🗓️ **Tareas de Cron (`crontab -l`):**\n\n```\n{proceso.stdout or '(Vacío)'}\n```"
        except Exception as e:
            salida = f"❌ **Error inesperado** al consultar cron: {e}"
        await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=admin_menu_keyboard())

    # Ejecución de acciones específicas (Scripts, Servicios)
    elif data.startswith('run:shell:'):
        script_name = data.split(':', 2)[2]
        config = cargar_configuracion()
        script_path = config["scripts_permitidos"][script_name]
        await query.edit_message_text(f"🚀 Ejecutando '{script_name}'...", parse_mode='Markdown')
        try:
            proceso = subprocess.run([script_path], capture_output=True, text=True, timeout=120, check=True)
            salida = f"✅ **Script '{script_name}' ejecutado con éxito.**\n\n--- Salida ---\n`{proceso.stdout or '(Sin salida)'}`"
            await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=dynamic_script_keyboard('shell'))
        except Exception as e:
            await query.edit_message_text(f"❌ Error al ejecutar {script_name}: {e}", reply_markup=dynamic_script_keyboard('shell'))

    elif data.startswith('run:python:'):
        script_name = data.split(':', 2)[2]
        config = cargar_configuracion()
        script_path = config["python_scripts_permitidos"][script_name]
        await query.edit_message_text(f"🐍 Ejecutando '{script_name}'...", parse_mode='Markdown')
        try:
            proceso = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=300, check=True)
            salida = f"✅ **Script '{script_name}' ejecutado con éxito.**\n\n--- Salida ---\n`{proceso.stdout or '(Sin salida)'}`"
            await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=dynamic_script_keyboard('python'))
        except Exception as e:
            await query.edit_message_text(f"❌ Error al ejecutar {script_name}: {e}", reply_markup=dynamic_script_keyboard('python'))

    elif data.startswith('service:'):
        service_name = data.split(':', 1)[1]
        await query.edit_message_text(f"🔎 Verificando estado de `{service_name}`...", parse_mode='Markdown')
        try:
            command = ['systemctl', 'status', service_name]
            proceso = subprocess.run(command, capture_output=True, text=True, timeout=10)
            output = proceso.stdout + proceso.stderr
            if "active (running)" in output: status_icon, status_text = "✅", "Activo"
            elif "inactive (dead)" in output: status_icon, status_text = "❌", "Inactivo"
            elif "failed" in output: status_icon, status_text = "🔥", "Ha fallado"
            else: status_icon, status_text = "❔", "Desconocido"

            log_lines = re.findall(r'●.*|Loaded:.*|Active:.*|Main PID:.*|(?<=─ ).*', output)
            detalle = "\n".join(log_lines[-5:])
            reporte = f"{status_icon} **Estado de `{service_name}`: {status_text}**\n\n```\n{detalle or 'No hay detalles.'}\n```"
            await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=dynamic_services_keyboard())
        except Exception as e:
             await query.edit_message_text(f"❌ Error al verificar {service_name}: {e}", reply_markup=dynamic_services_keyboard())

    # Acciones de Gestión de Archivos
    elif data.startswith('files:list_'):
        folder_type = data.split('_')[1]
        folder_key = "image_directory" if folder_type == 'imagenes' else "file_directory"
        config = cargar_configuracion()
        target_dir = os.path.expanduser(config.get(folder_key, ''))
        if not target_dir or not os.path.isdir(target_dir):
            await query.edit_message_text(f"❌ La carpeta para `{folder_type}` no está configurada o no existe.", parse_mode='Markdown', reply_markup=files_menu_keyboard())
            return
        files = os.listdir(target_dir)
        if not files:
            message = f"ℹ️ La carpeta `{folder_type}` está vacía."
        else:
            file_list_str = "\n".join(f"`{escape_markdown(f)}`" for f in files)
            message = f"📁 **Archivos en `{folder_type}`:**\n{file_list_str}\n\nPara descargar un archivo, usa el comando `/get {folder_type} nombre_del_archivo`"
        if len(message) > 4096: message = message[:4090] + "\n..."
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=files_menu_keyboard())


# --- MANEJADORES DE COMANDOS DE RED (REFACTORIZADOS) ---
async def _handle_network_command(update: Update, context: ContextTypes.DEFAULT_TYPE, tool_func, usage: str, message: str):
    """Función auxiliar para manejar comandos de red."""
    if not context.args:
        await update.message.reply_text(f"Uso: {usage}")
        return
    host = context.args[0]
    await update.message.reply_text(f"{message} `{host}`...", parse_mode='Markdown')
    result = tool_func(host)
    await update.message.reply_text(result, parse_mode='Markdown')

@authorized_only
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_network_command(update, context, do_ping, "/ping <host_o_ip>", "📡 Haciendo ping a")

@authorized_only
async def traceroute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_network_command(update, context, do_traceroute, "/traceroute <host_o_ip>", "🗺️ Ejecutando traceroute a")

@authorized_only
async def nmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_network_command(update, context, do_nmap, "/nmap <host_o_ip>", "🔬 Ejecutando escaneo Nmap a")

# --- NUEVOS COMANDOS DE AYUDA Y GESTIÓN DE USUARIOS ---
@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra un mensaje de ayuda detallado."""
    help_text = (
        "ℹ️ **Ayuda del Bot Interactivo**\n\n"
        "Aquí tienes un resumen de los comandos y funciones disponibles:\n\n"
        "**Comandos Directos:**\n"
        "`/start` - Inicia la conversación y muestra el menú principal.\n"
        "`/help` - Muestra este mensaje de ayuda.\n"
        "`/ping <host>` - Lanza 4 pings al host especificado.\n"
        "`/traceroute <host>` - Realiza un traceroute al host.\n"
        "`/nmap <host>` - Ejecuta un escaneo `nmap -A` (puede tardar).\n"
        "`/get <imagenes|ficheros> <nombre_archivo>` - Descarga un archivo del servidor.\n\n"
        "**Menús Interactivos:**\n"
        "Puedes navegar por los menús para acceder a la mayoría de funciones de forma sencilla, incluyendo:\n"
        "- **Monitorización**: Ver el estado general, recursos locales y estado de servicios.\n"
        "- **Administración**: Ejecutar scripts y ver tareas cron.\n"
        "- **Herramientas de Red**: Acceder a Ping, Traceroute y Nmap desde una lista.\n"
        "- **Gestión de Archivos**: Listar y subir archivos/imágenes.\n\n"
        "**Gestión de Usuarios (Solo Super Admin):**\n"
        "`/adduser <ID de usuario>` - Añade un nuevo usuario autorizado.\n"
        "`/deluser <ID de usuario>` - Elimina un usuario autorizado."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

@super_admin_only
async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Añade un nuevo ID de usuario a la lista de autorizados."""
    if not context.args:
        await update.message.reply_text("Uso: `/adduser <ID_de_usuario_de_Telegram>`")
        return

    try:
        new_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return

    config = cargar_configuracion()
    authorized_users = config["telegram"]["authorized_users"]

    if new_user_id in authorized_users:
        await update.message.reply_text(f"ℹ️ El usuario `{new_user_id}` ya está autorizado.")
    else:
        config["telegram"]["authorized_users"].append(new_user_id)
        if guardar_configuracion(config):
            await update.message.reply_text(f"✅ Usuario `{new_user_id}` añadido correctamente.")
            logging.info(f"Usuario {new_user_id} añadido por {update.effective_user.id}")
        else:
            await update.message.reply_text("❌ Error al guardar la configuración.")

@super_admin_only
async def deluser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina un ID de usuario de la lista de autorizados."""
    if not context.args:
        await update.message.reply_text("Uso: `/deluser <ID_de_usuario_de_Telegram>`")
        return

    try:
        user_to_delete = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return

    config = cargar_configuracion()
    
    if user_to_delete == config.get("telegram", {}).get("super_admin_id"):
        await update.message.reply_text("⛔ No puedes eliminar al super administrador.")
        return

    authorized_users = config["telegram"]["authorized_users"]

    if user_to_delete in authorized_users:
        config["telegram"]["authorized_users"].remove(user_to_delete)
        if guardar_configuracion(config):
            await update.message.reply_text(f"✅ Usuario `{user_to_delete}` eliminado correctamente.")
            logging.info(f"Usuario {user_to_delete} eliminado por {update.effective_user.id}")
        else:
            await update.message.reply_text("❌ Error al guardar la configuración.")
    else:
        await update.message.reply_text(f"ℹ️ El usuario `{user_to_delete}` no se encuentra en la lista.")


# --- MANEJADORES DE ARCHIVOS ---
@authorized_only
async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    config = cargar_configuracion()
    is_photo = bool(update.message.photo)
    if is_photo:
        target_dir_key = "image_directory"
        file_to_download = update.message.photo[-1]
        original_name = f"{file_to_download.file_id}.jpg"
    else:
        target_dir_key = "file_directory"
        file_to_download = update.message.document
        original_name = file_to_download.file_name

    target_dir = config.get(target_dir_key)
    if not target_dir:
        await update.message.reply_text(f"❌ La carpeta de destino `{target_dir_key}` no está configurada.")
        return

    expanded_dir = os.path.expanduser(target_dir)
    sanitized_name = os.path.basename(original_name).replace("..", "")
    destination_path = os.path.join(expanded_dir, sanitized_name)

    try:
        os.makedirs(expanded_dir, exist_ok=True)
        file = await context.bot.get_file(file_to_download.file_id)
        await file.download_to_drive(destination_path)
        logging.info(f"Archivo '{sanitized_name}' subido a '{expanded_dir}' por el usuario {update.effective_user.id}")
        await update.message.reply_text(f"✅ Archivo `{escape_markdown(sanitized_name)}` guardado.", parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Error al subir archivo: {e}")
        await update.message.reply_text(f"❌ Ocurrió un error: `{escape_markdown(str(e))}`", parse_mode='Markdown')

@authorized_only
async def get_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2 or context.args[0] not in ['imagenes', 'ficheros']:
        await update.message.reply_text("Uso: `/get [imagenes|ficheros] [nombre_del_archivo]`", parse_mode='Markdown')
        return

    folder_type = context.args[0]
    filename = " ".join(context.args[1:])
    folder_key = "image_directory" if folder_type == 'imagenes' else "file_directory"
    config = cargar_configuracion()
    base_dir = os.path.expanduser(config.get(folder_key, ''))
    safe_filename = os.path.basename(filename)
    if safe_filename != filename:
        await update.message.reply_text("❌ Nombre de archivo inválido.", parse_mode='Markdown')
        return
    file_path = os.path.join(base_dir, safe_filename)
    if os.path.abspath(file_path).startswith(os.path.abspath(base_dir)) and os.path.exists(file_path):
        await update.message.reply_text(f"🚀 Enviando `{escape_markdown(safe_filename)}`...", parse_mode='Markdown')
        try:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
        except Exception as e:
            await update.message.reply_text(f"❌ Error al enviar el archivo: `{escape_markdown(str(e))}`", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ El archivo `{escape_markdown(safe_filename)}` no se encuentra.", parse_mode='Markdown')

# --- MOTOR PRINCIPAL DEL BOT ---
def main():
    config = cargar_configuracion()
    token = config.get("telegram", {}).get("token")
    if not token:
        logging.error("No se encontró el token de Telegram.")
        sys.exit()

    application = Application.builder().token(token).build()

    # Registro de Manejadores
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # Comandos de red
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("traceroute", traceroute_command))
    application.add_handler(CommandHandler("nmap", nmap_command))
    
    # NUEVOS MANEJADORES DE AYUDA Y USUARIOS
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("adduser", adduser_command))
    application.add_handler(CommandHandler("deluser", deluser_command))

    # Otros manejadores
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file_upload))
    application.add_handler(CommandHandler("get", get_file))

    logging.info("El bot se ha iniciado y está escuchando...")
    application.run_polling()

if __name__ == "__main__":
    main()
