#Bot interactivo telegram Version 1.5
#Por Óscar Giménez Blasco y GEMINI para menus, apariencia y monitor.
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
import time # Añadido para las comprobaciones periódicas
import threading # Añadido para el monitoreo en segundo plano
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

CONFIG_FILE = '/home/TU_USUARIO/telegram-admin-bot/config/configbot.json'

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
        except AttributeError: # getloadavg might not be available on all OSes (e.g., Windows)
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
        if servidor.get("chequeos", {}).get("ping"):
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

def do_dig(domain: str) -> str: # NUEVA FUNCIÓN DIG
    """Realiza una consulta DNS (dig)."""
    try:
        proc = subprocess.run(['dig', domain], capture_output=True, text=True, timeout=30)
        output = proc.stdout or proc.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n\n... (salida truncada)"
        return f"🌐 **Resultado de DIG para `{domain}`:**\n```\n{output}\n```"
    except FileNotFoundError:
        return "❌ Error: El comando `dig` no se encuentra. ¿Está instalado?"
    except subprocess.TimeoutExpired:
        return f"❌ Error: Timeout (30s) durante la consulta `dig`."
    except Exception as e:
        return f"❌ Error inesperado: {e}"

def do_whois(domain: str) -> str: # NUEVA FUNCIÓN WHOIS
    """Realiza una consulta WHOIS."""
    try:
        proc = subprocess.run(['whois', domain], capture_output=True, text=True, timeout=30)
        output = proc.stdout or proc.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n\n... (salida truncada)"
        return f"👤 **Resultado de WHOIS para `{domain}`:**\n```\n{output}\n```"
    except FileNotFoundError:
        return "❌ Error: El comando `whois` no se encuentra. ¿Está instalado?"
    except subprocess.TimeoutExpired:
        return f"❌ Error: Timeout (30s) durante la consulta `whois`."
    except Exception as e:
        return f"❌ Error inesperado: {e}"

# --- NUEVAS FUNCIONES DE MONITOREO Y ADMINISTRACIÓN ---

def get_disk_usage_text() -> str: # NUEVA FUNCIÓN DF -H
    """Obtiene el uso de disco con 'df -h'."""
    try:
        proc = subprocess.run(['df', '-h'], capture_output=True, text=True, timeout=10, check=True)
        return f"💾 **Uso de Disco (`df -h`)**:\n```\n{proc.stdout}\n```"
    except FileNotFoundError:
        return "❌ Error: El comando `df` no se encuentra."
    except subprocess.CalledProcessError as e:
        return f"❌ Error al ejecutar `df -h`: {e.stderr}"
    except Exception as e:
        return f"❌ Error inesperado: {e}"

def get_processes_text() -> str: # NUEVA FUNCIÓN PS AUX
    """Lista los procesos con 'ps aux'."""
    try:
        proc = subprocess.run(['ps', 'aux'], capture_output=True, text=True, timeout=30, check=True)
        output = proc.stdout
        if len(output) > 4000: # Truncar si es muy largo
            output = output[:3900] + "\n... (salida truncada)"
        return f"⚙️ **Procesos (`ps aux`)**:\n```\n{output}\n```"
    except FileNotFoundError:
        return "❌ Error: El comando `ps` no se encuentra."
    except subprocess.CalledProcessError as e:
        return f"❌ Error al ejecutar `ps aux`: {e.stderr}"
    except Exception as e:
        return f"❌ Error inesperado: {e}"

def get_system_info_text() -> str: # NUEVA FUNCIÓN UNAME -A
    """Obtiene información del sistema con 'uname -a'."""
    try:
        uname_output = subprocess.run(['uname', '-a'], capture_output=True, text=True, timeout=5, check=True).stdout
        lsb_output = ""
        try: # Intentar lsb_release si existe
            lsb_output = subprocess.run(['lsb_release', '-a'], capture_output=True, text=True, timeout=5, check=True).stdout
        except FileNotFoundError:
            pass # No pasa nada si lsb_release no está
        
        response = f"ℹ️ **Información del Sistema**:\n"
        response += f"```\n{uname_output}\n```\n"
        if lsb_output and "No LSB modules are available" not in lsb_output:
            response += f"📦 *Distribución:*\n```\n{lsb_output}\n```"
        else:
            response += "📦 *Distribución: LSB release no encontrado. Intenta 'cat /etc/*release' para más info.*"
        return response
    except Exception as e:
        return f"❌ Error inesperado al obtener info del sistema: {e}"

def get_log_lines(log_alias: str, num_lines: int) -> str: # NUEVA FUNCIÓN PARA LOGS
    """Obtiene las últimas N líneas de un log permitido."""
    config = cargar_configuracion()
    log_path = config.get("allowed_logs", {}).get(log_alias)
    if not log_path:
        return f"❌ El log '{log_alias}' no está permitido o no existe en la configuración."
    
    try:
        proc = subprocess.run(['tail', '-n', str(num_lines), log_path], capture_output=True, text=True, timeout=30, check=True)
        output = proc.stdout
        if len(output) > 4000:
            output = output[:3900] + "\n... (salida truncada)"
        return f"📜 **Últimas {num_lines} líneas de `{log_alias}`:**\n```\n{output}\n```"
    except FileNotFoundError:
        return "❌ Error: El comando `tail` no se encuentra."
    except subprocess.CalledProcessError as e:
        return f"❌ Error al leer el log `{log_alias}`: {e.stderr}"
    except Exception as e:
        return f"❌ Error inesperado: {e}"

def search_log(log_alias: str, pattern: str) -> str: # NUEVA FUNCIÓN PARA BUSCAR EN LOGS
    """Busca un patrón en un log permitido."""
    config = cargar_configuracion()
    log_path = config.get("allowed_logs", {}).get(log_alias)
    if not log_path:
        return f"❌ El log '{log_alias}' no está permitido o no existe en la configuración."
    
    try:
        proc = subprocess.run(['grep', '-i', pattern, log_path], capture_output=True, text=True, timeout=60, check=True)
        output = proc.stdout
        if not output.strip():
            return f"🔍 No se encontraron coincidencias para '{pattern}' en `{log_alias}`."
        if len(output) > 4000:
            output = output[:3900] + "\n... (salida truncada)"
        return f"🔍 **Resultados para '{pattern}' en `{log_alias}`:**\n```\n{output}\n```"
    except FileNotFoundError:
        return "❌ Error: El comando `grep` no se encuentra."
    except subprocess.CalledProcessError as e:
        # grep retorna 1 si no encuentra el patrón, lo cual no es un error
        if e.returncode == 1:
            return f"🔍 No se encontraron coincidencias para '{pattern}' en `{log_alias}`."
        return f"❌ Error al buscar en el log `{log_alias}`: {e.stderr}"
    except Exception as e:
        return f"❌ Error inesperado: {e}"

def docker_command(action: str, container_name: str = None, num_lines: int = 10) -> str: # NUEVA FUNCIÓN DOCKER
    """Ejecuta comandos de Docker: ps, logs, restart."""
    config = cargar_configuracion()
    docker_allowed = config.get("docker_containers_allowed", [])

    if action == 'ps':
        try:
            proc = subprocess.run(['docker', 'ps', '--format', 'table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}'], capture_output=True, text=True, timeout=20, check=True)
            return f"🐳 **Contenedores Docker Activos:**\n```\n{proc.stdout}\n```"
        except FileNotFoundError:
            return "❌ Error: El comando `docker` no se encuentra. ¿Está instalado?"
        except subprocess.CalledProcessError as e:
            return f"❌ Error al listar contenedores: {e.stderr}"
        except Exception as e:
            return f"❌ Error inesperado: {e}"
    
    # Para logs y restart, se necesita un nombre de contenedor
    if not container_name:
        return "❌ Se requiere el nombre del contenedor para esta acción."
    
    if container_name not in docker_allowed:
        return f"❌ El contenedor '{container_name}' no está permitido en la configuración."

    if action == 'logs':
        try:
            proc = subprocess.run(['docker', 'logs', '--tail', str(num_lines), container_name], capture_output=True, text=True, timeout=60, check=True)
            output = proc.stdout
            if len(output) > 4000:
                output = output[:3900] + "\n... (salida truncada)"
            return f"📜 **Logs de `{container_name}` (últimas {num_lines} líneas):**\n```\n{output}\n```"
        except subprocess.CalledProcessError as e:
            return f"❌ Error al obtener logs de `{container_name}`: {e.stderr}"
        except Exception as e:
            return f"❌ Error inesperado: {e}"
    
    elif action == 'restart':
        try:
            proc = subprocess.run(['sudo', 'docker', 'restart', container_name], capture_output=True, text=True, timeout=30, check=True)
            return f"🔄 **Contenedor `{container_name}` Reiniciado:**\n```\n{proc.stdout or proc.stderr}\n```"
        except subprocess.CalledProcessError as e:
            return f"❌ Error al reiniciar `{container_name}`: {e.stderr}. Asegúrate de que el usuario del bot tenga permisos sudo NOPASSWD para 'docker restart'."
        except Exception as e:
            return f"❌ Error inesperado: {e}"
    
    return "❌ Acción de Docker no reconocida."


# --- MENÚS ---
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📊 Monitorización", callback_data='menu:monitor')],
        [InlineKeyboardButton("⚙️ Administración", callback_data='menu:admin')],
        [InlineKeyboardButton("🛠️ Herramientas de Red", callback_data='menu:network_tools')],
        [InlineKeyboardButton("🐳 Gestión Docker", callback_data='menu:docker')], # NUEVO
        [InlineKeyboardButton("📁 Gestión de Archivos", callback_data='menu:files')],
        [InlineKeyboardButton("🔄 Actualizar", callback_data='refresh_main')]
    ]
    return InlineKeyboardMarkup(keyboard)

def monitor_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("Sistemas (Status General)", callback_data='monitor:status_all')],
        [InlineKeyboardButton("Recursos Locales (CPU/RAM)", callback_data='monitor:resources')],
        [InlineKeyboardButton("Uso de Disco (`df -h`)", callback_data='monitor:disk')], # NUEVO
        [InlineKeyboardButton("Procesos (`ps aux`)", callback_data='monitor:processes')], # NUEVO
        [InlineKeyboardButton("Info. Sistema (`uname -a`)", callback_data='monitor:systeminfo')], # NUEVO
        [InlineKeyboardButton("Ver Logs", callback_data='menu:logs')], # NUEVO
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
        [InlineKeyboardButton("🌐 Dig (DNS Lookup)", callback_data='network:select_dig')], # NUEVO
        [InlineKeyboardButton("👤 Whois", callback_data='network:select_whois')], # NUEVO
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

def dynamic_logs_keyboard(): # NUEVO MENÚ DE LOGS
    config = cargar_configuracion()
    logs = config.get("allowed_logs", {})
    keyboard = []
    for alias in logs.keys():
        keyboard.append([InlineKeyboardButton(f"Ver '{alias}'", callback_data=f"log:view:{alias}")])
    keyboard.append([InlineKeyboardButton("⬅️ Volver a Monitor", callback_data='menu:monitor')])
    return InlineKeyboardMarkup(keyboard)

def docker_menu_keyboard(): # NUEVO MENÚ DE DOCKER
    config = cargar_configuracion()
    containers = config.get("docker_containers_allowed", [])
    keyboard = [
        [InlineKeyboardButton("Listar Contenedores (`docker ps`)", callback_data='docker:ps')]
    ]
    if containers:
        keyboard.append([InlineKeyboardButton("Ver Logs de Contenedor", callback_data='docker:select_logs')])
        keyboard.append([InlineKeyboardButton("Reiniciar Contenedor", callback_data='docker:select_restart')])
    keyboard.append([InlineKeyboardButton("⬅️ Volver", callback_data='menu:main')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_docker_container_keyboard(action: str): # NUEVO MENÚ DINÁMICO PARA DOCKER
    config = cargar_configuracion()
    containers = config.get("docker_containers_allowed", [])
    keyboard = []
    for container in containers:
        keyboard.append([InlineKeyboardButton(f"{action.capitalize()} '{container}'", callback_data=f"docker:{action}:{container}")])
    keyboard.append([InlineKeyboardButton("⬅️ Volver a Docker", callback_data='menu:docker')])
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
        await query.edit_message_text(text="🛠️ Herramientas de Red\n\nElige una herramienta del menú o escribe el comando directamente (ej: `/nmap 8.8.8.8`).", parse_mode='Markdown', reply_markup=network_tools_menu_keyboard())
    elif data == 'menu:docker': # NUEVO MANEJADOR DE MENÚ DOCKER
        await query.edit_message_text(text="🐳 Gestión Docker\n\nElige una opción para interactuar con tus contenedores Docker.", parse_mode='Markdown', reply_markup=docker_menu_keyboard())
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
    elif data == 'network:select_dig': # NUEVO: SELECTOR DE DIG
        texto = "🌐 **Dig (DNS Lookup)**\n\nSelecciona un objetivo de la lista o escribe el comando directamente.\n*Ejemplo: `/dig example.com`*"
        await query.edit_message_text(texto, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('dig'))
    elif data == 'network:select_whois': # NUEVO: SELECTOR DE WHOIS
        texto = "👤 **Whois**\n\nSelecciona un objetivo de la lista o escribe el comando directamente.\n*Ejemplo: `/whois example.com`*"
        await query.edit_message_text(texto, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('whois'))

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
    elif data.startswith('run:dig:'): # NUEVO: EJECUCIÓN DIG
        domain = data.split(':', 2)[2]
        await query.edit_message_text(f"🌐 Realizando consulta DIG para `{domain}`...", parse_mode='Markdown')
        result = do_dig(domain)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('dig'))
    elif data.startswith('run:whois:'): # NUEVO: EJECUCIÓN WHOIS
        domain = data.split(':', 2)[2]
        await query.edit_message_text(f"👤 Realizando consulta WHOIS para `{domain}`...", parse_mode='Markdown')
        result = do_whois(domain)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_host_keyboard('whois'))

    # Acciones de Monitorización
    elif data == 'monitor:status_all':
        await query.edit_message_text("🔍 Obteniendo estado de todos los servidores...", parse_mode='Markdown')
        reporte = get_status_report_text()
        await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard())
    elif data == 'monitor:resources':
        await query.edit_message_text("📊 Recopilando información de los recursos del sistema...", parse_mode='Markdown')
        reporte = get_resources_text()
        await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard())
    elif data == 'monitor:disk': # NUEVO: USO DE DISCO
        await query.edit_message_text("💾 Obteniendo uso de disco...", parse_mode='Markdown')
        reporte = get_disk_usage_text()
        await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard())
    elif data == 'monitor:processes': # NUEVO: LISTAR PROCESOS
        await query.edit_message_text("⚙️ Listando procesos...", parse_mode='Markdown')
        reporte = get_processes_text()
        await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard())
    elif data == 'monitor:systeminfo': # NUEVO: INFO DEL SISTEMA
        await query.edit_message_text("ℹ️ Obteniendo información del sistema...", parse_mode='Markdown')
        reporte = get_system_info_text()
        await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard())
    elif data == 'menu:logs': # NUEVO: SELECCIONAR LOG
        await query.edit_message_text("Selecciona un log para ver o buscar:", reply_markup=dynamic_logs_keyboard())

    # Acciones de Logs
    elif data.startswith('log:view:'): # NUEVO: VER LOGS
        log_alias = data.split(':', 2)[2]
        await query.edit_message_text(f"📜 Obteniendo últimas 20 líneas de `{log_alias}`...", parse_mode='Markdown')
        result = get_log_lines(log_alias, 20) # Por defecto 20 líneas
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_logs_keyboard())
    # NOTA: La búsqueda en logs no se puede hacer desde un botón simple sin input. Se requerirá comando.

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
    
    # Acciones de Docker
    elif data == 'docker:ps': # NUEVO: LISTAR DOCKER PS
        await query.edit_message_text("🐳 Listando contenedores Docker...", parse_mode='Markdown')
        result = docker_command('ps')
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=docker_menu_keyboard())
    elif data == 'docker:select_logs': # NUEVO: SELECTOR DE LOGS DOCKER
        await query.edit_message_text("Selecciona el contenedor para ver sus logs:", reply_markup=dynamic_docker_container_keyboard('logs'))
    elif data == 'docker:select_restart': # NUEVO: SELECTOR DE RESTART DOCKER
        await query.edit_message_text("Selecciona el contenedor para reiniciar:", reply_markup=dynamic_docker_container_keyboard('restart'))
    elif data.startswith('docker:logs:'): # NUEVO: EJECUCION LOGS DOCKER
        container_name = data.split(':', 2)[2]
        await query.edit_message_text(f"📜 Obteniendo logs de `{container_name}`...", parse_mode='Markdown')
        result = docker_command('logs', container_name, 20) # Por defecto 20 líneas
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_docker_container_keyboard('logs'))
    elif data.startswith('docker:restart:'): # NUEVO: EJECUCION RESTART DOCKER
        container_name = data.split(':', 2)[2]
        await query.edit_message_text(f"🔄 Reiniciando contenedor `{container_name}`...", parse_mode='Markdown')
        result = docker_command('restart', container_name)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_docker_container_keyboard('restart'))


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
async def _handle_network_command(update: Update, context: ContextTypes.DEFAULT_TYPE, tool_func, usage: str, message_prefix: str):
    """Función auxiliar para manejar comandos de red."""
    if not context.args:
        await update.message.reply_text(f"Uso: {usage}")
        return
    host_or_domain = context.args[0]
    await update.message.reply_text(f"{message_prefix} `{host_or_domain}`...", parse_mode='Markdown')
    result = tool_func(host_or_domain)
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

@authorized_only
async def dig_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # NUEVO COMANDO DIG
    await _handle_network_command(update, context, do_dig, "/dig <dominio>", "🌐 Realizando consulta DIG para")

@authorized_only
async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # NUEVO COMANDO WHOIS
    await _handle_network_command(update, context, do_whois, "/whois <dominio>", "👤 Realizando consulta WHOIS para")

# --- NUEVOS COMANDOS DE MONITOREO DIRECTO ---
@authorized_only
async def resources_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📊 Recopilando información de los recursos del sistema...", parse_mode='Markdown')
    reporte = get_resources_text()
    await update.message.reply_text(reporte, parse_mode='Markdown')

@authorized_only
async def disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💾 Obteniendo uso de disco...", parse_mode='Markdown')
    reporte = get_disk_usage_text()
    await update.message.reply_text(reporte, parse_mode='Markdown')

@authorized_only
async def processes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚙️ Listando procesos...", parse_mode='Markdown')
    reporte = get_processes_text()
    await update.message.reply_text(reporte, parse_mode='Markdown')

@authorized_only
async def systeminfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Obteniendo información del sistema...", parse_mode='Markdown')
    reporte = get_system_info_text()
    await update.message.reply_text(reporte, parse_mode='Markdown')

@authorized_only
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # NUEVO COMANDO LOGS
    if not context.args:
        # Si no hay argumentos, ofrecer los logs disponibles
        config = cargar_configuracion()
        available_logs = ", ".join(config.get("allowed_logs", {}).keys())
        await update.message.reply_text(f"Uso: `/logs <nombre_log> [lineas]` o `/logs search <nombre_log> <patron>`\nLogs disponibles: `{available_logs}`", parse_mode='Markdown')
        return

    action = context.args[0]
    if action == 'search':
        if len(context.args) < 3:
            await update.message.reply_text("Uso: `/logs search <nombre_log> <patron>`", parse_mode='Markdown')
            return
        log_alias = context.args[1]
        pattern = " ".join(context.args[2:])
        await update.message.reply_text(f"🔍 Buscando '{pattern}' en `{log_alias}`...", parse_mode='Markdown')
        result = search_log(log_alias, pattern)
        await update.message.reply_text(result, parse_mode='Markdown')
    else: # Default: ver últimas N líneas
        log_alias = context.args[0]
        num_lines = 20 # Default
        if len(context.args) > 1:
            try:
                num_lines = int(context.args[1])
                if num_lines < 1 or num_lines > 200: # Limitar para evitar sobrecarga
                    num_lines = 20
            except ValueError:
                pass # Usar default si no es un número
        
        await update.message.reply_text(f"📜 Obteniendo últimas {num_lines} líneas de `{log_alias}`...", parse_mode='Markdown')
        result = get_log_lines(log_alias, num_lines)
        await update.message.reply_text(result, parse_mode='Markdown')

@authorized_only
async def docker_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE): # NUEVO COMANDO DOCKER GLOBAL
    if not context.args:
        await update.message.reply_text("Uso: `/docker <ps|logs|restart> [contenedor] [lineas]`", parse_mode='Markdown')
        return
    
    action = context.args[0]
    
    if action == 'ps':
        await update.message.reply_text("🐳 Listando contenedores Docker...", parse_mode='Markdown')
        result = docker_command('ps')
        await update.message.reply_text(result, parse_mode='Markdown')
    elif action == 'logs':
        if len(context.args) < 2:
            await update.message.reply_text("Uso: `/docker logs <contenedor> [lineas]`", parse_mode='Markdown')
            return
        container_name = context.args[1]
        num_lines = 20
        if len(context.args) > 2:
            try:
                num_lines = int(context.args[2])
                if num_lines < 1 or num_lines > 200:
                    num_lines = 20
            except ValueError:
                pass
        await update.message.reply_text(f"📜 Obteniendo logs de `{container_name}`...", parse_mode='Markdown')
        result = docker_command('logs', container_name, num_lines)
        await update.message.reply_text(result, parse_mode='Markdown')
    elif action == 'restart':
        if len(context.args) < 2:
            await update.message.reply_text("Uso: `/docker restart <contenedor>`", parse_mode='Markdown')
            return
        container_name = context.args[1]
        await update.message.reply_text(f"🔄 Reiniciando contenedor `{container_name}`...", parse_mode='Markdown')
        result = docker_command('restart', container_name)
        await update.message.reply_text(result, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Acción de Docker no reconocida. Usos: `ps`, `logs`, `restart`.", parse_mode='Markdown')

@super_admin_only
async def updates_command(update: Update, context: ContextTypes.DEFAULT_TYPE): # NUEVO COMANDO UPDATES
    await update.message.reply_text("Buscando actualizaciones de paquetes disponibles...", parse_mode='Markdown')
    try:
        # sudo apt update
        update_proc = subprocess.run(['sudo', 'apt', 'update'], capture_output=True, text=True, timeout=120)
        if update_proc.returncode != 0:
            await update.message.reply_text(f"❌ Error al ejecutar `sudo apt update`:\n```\n{update_proc.stderr}\n```", parse_mode='Markdown')
            return

        # apt list --upgradable
        list_proc = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True, text=True, timeout=30)
        if list_proc.returncode != 0:
            await update.message.reply_text(f"❌ Error al ejecutar `apt list --upgradable`:\n```\n{list_proc.stderr}\n```", parse_mode='Markdown')
            return
        
        upgradable_packages = [line for line in list_proc.stdout.splitlines() if not line.startswith('Listing...')]
        if upgradable_packages:
            response = "📦 *Actualizaciones de paquetes disponibles:*\n```\n" + "\n".join(upgradable_packages) + "\n```"
            response += "\n\nPara actualizar, ejecuta `sudo apt upgrade` manualmente en el servidor."
        else:
            response = "✅ No hay actualizaciones de paquetes disponibles."
        await update.message.reply_text(response, parse_mode='Markdown')

        # Actualizar el timestamp de la última comprobación
        config = cargar_configuracion()
        config['monitoring_thresholds']['last_update_check'] = time.time()
        guardar_configuracion(config)

    except FileNotFoundError:
        await update.message.reply_text("❌ Error: Los comandos `apt` o `sudo` no se encuentran. ¿Es un sistema basado en Debian/Ubuntu?", parse_mode='Markdown')
    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Timeout al buscar actualizaciones. La operación tardó demasiado.", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error inesperado al comprobar actualizaciones: `{escape_markdown(str(e))}`", parse_mode='Markdown')

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
        "`/resources` - Muestra el uso de CPU, RAM y Disco principal.\n" # NUEVO
        "`/disk` - Muestra el uso de disco detallado (`df -h`).\n" # NUEVO
        "`/processes` - Lista los procesos en ejecución (`ps aux`).\n" # NUEVO
        "`/systeminfo` - Muestra información del sistema (`uname -a`, `lsb_release -a`).\n" # NUEVO
        "`/dig <dominio>` - Realiza una consulta DNS.\n" # NUEVO
        "`/whois <dominio>` - Obtiene información WHOIS de un dominio.\n" # NUEVO
        "`/logs <nombre_log> [lineas]` - Ver últimas N líneas de un log permitido (ej: `/logs syslog 20`).\n" # NUEVO
        "`/logs search <nombre_log> <patron>` - Buscar en un log permitido (ej: `/logs auth 'failed password'`).\n" # NUEVO
        "`/docker <ps|logs|restart> [contenedor] [lineas]` - Gestiona contenedores Docker. (ej: `/docker ps`, `/docker logs my_app`, `/docker restart db_server`).\n" # NUEVO
        "`/updates` - (Solo Super Admin) Busca actualizaciones de paquetes APT disponibles.\n\n" # NUEVO
        "`/get <imagenes|ficheros> <nombre_archivo>` - Descarga un archivo del servidor.\n\n"
        "**Menús Interactivos:**\n"
        "Puedes navegar por los menús para acceder a la mayoría de funciones de forma sencilla, incluyendo:\n"
        "- **Monitorización**: Ver el estado general, recursos locales, uso de disco, procesos, logs y estado de servicios.\n" # ACTUALIZADO
        "- **Administración**: Ejecutar scripts y ver tareas cron.\n"
        "- **Herramientas de Red**: Acceder a Ping, Traceroute, Nmap, Dig y Whois.\n" # ACTUALIZADO
        "- **Gestión Docker**: Listar, ver logs y reiniciar contenedores Docker.\n" # NUEVO
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
        await update.message.reply_text("Uso: `/adduser <ID_de_usuario_de_Telegram>`", parse_mode='Markdown')
        return

    try:
        new_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ El ID debe ser un número.")
        return

    config = cargar_configuracion()
    authorized_users = config["telegram"]["authorized_users"]

    if new_user_id in authorized_users:
        await update.message.reply_text(f"ℹ️ El usuario `{new_user_id}` ya está autorizado.", parse_mode='Markdown')
    else:
        config["telegram"]["authorized_users"].append(new_user_id)
        if guardar_configuracion(config):
            await update.message.reply_text(f"✅ Usuario `{new_user_id}` añadido correctamente.", parse_mode='Markdown')
            logging.info(f"Usuario {new_user_id} añadido por {update.effective_user.id}")
        else:
            await update.message.reply_text("❌ Error al guardar la configuración.")

@super_admin_only
async def deluser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina un ID de usuario de la lista de autorizados."""
    if not context.args:
        await update.message.reply_text("Uso: `/deluser <ID_de_usuario_de_Telegram>`", parse_mode='Markdown')
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
            await update.message.reply_text(f"✅ Usuario `{user_to_delete}` eliminado correctamente.", parse_mode='Markdown')
            logging.info(f"Usuario {user_to_delete} eliminado por {update.effective_user.id}")
        else:
            await update.message.reply_text("❌ Error al guardar la configuración.")
    else:
        await update.message.reply_text(f"ℹ️ El usuario `{user_to_delete}` no se encuentra en la lista.", parse_mode='Markdown')


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
        await update.message.reply_text(f"❌ La carpeta de destino `{target_dir_key}` no está configurada.", parse_mode='Markdown')
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

# --- FUNCIONES DE MONITOREO PROACTIVO ---

async def periodic_checks(application: Application):
    """Función que ejecuta las comprobaciones periódicas."""
    bot_instance = application.bot
    while True:
        config = cargar_configuracion() # Cargar la configuración fresca en cada ciclo
        monitoring_thresholds = config.get("monitoring_thresholds", {})
        super_admin_id = config.get("telegram", {}).get("super_admin_id")

        current_time = time.time()
        check_interval_seconds = monitoring_thresholds.get('check_interval_minutes', 5) * 60
        update_check_interval_seconds = monitoring_thresholds.get('update_check_interval_hours', 24) * 3600

        # --- Check CPU Usage ---
        last_cpu_check = monitoring_thresholds.get('last_cpu_check', 0)
        if current_time - last_cpu_check > check_interval_seconds:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                if cpu_percent > monitoring_thresholds.get('cpu_usage_percent', 90):
                    await bot_instance.send_message(super_admin_id, 
                                                    f"⚠️ ALERTA CPU: El uso de CPU ha superado el {monitoring_thresholds['cpu_usage_percent']}% ({cpu_percent:.1f}% actual).", 
                                                    parse_mode='Markdown')
                    logging.warning(f"Alerta de CPU: {cpu_percent}%")
                config['monitoring_thresholds']['last_cpu_check'] = current_time
                guardar_configuracion(config)
            except Exception as e:
                logging.error(f"Error en check_cpu_usage: {e}")

        # --- Check Disk Usage ---
        last_disk_check = monitoring_thresholds.get('last_disk_check', 0)
        if current_time - last_disk_check > check_interval_seconds:
            try:
                disk = psutil.disk_usage('/')
                if disk.percent > monitoring_thresholds.get('disk_usage_percent', 95):
                    await bot_instance.send_message(super_admin_id, 
                                                    f"⚠️ ALERTA DISCO: El uso de disco raíz (/) ha superado el {monitoring_thresholds['disk_usage_percent']}% ({disk.percent:.1f}% actual).", 
                                                    parse_mode='Markdown')
                    logging.warning(f"Alerta de Disco: {disk.percent}%")
                config['monitoring_thresholds']['last_disk_check'] = current_time
                guardar_configuracion(config)
            except Exception as e:
                logging.error(f"Error en check_disk_usage: {e}")

        # --- Check for APT Updates ---
        last_update_check = monitoring_thresholds.get('last_update_check', 0)
        if current_time - last_update_check > update_check_interval_seconds:
            try:
                logging.info("Realizando comprobación periódica de actualizaciones...")
                subprocess.run(['sudo', 'apt', 'update'], capture_output=True, text=True, timeout=120)
                list_proc = subprocess.run(['apt', 'list', '--upgradable'], capture_output=True, text=True, timeout=30)
                
                upgradable_packages = [line for line in list_proc.stdout.splitlines() if not line.startswith('Listing...')]
                if upgradable_packages:
                    message = "🚨 *NOTIFICACIÓN DE ACTUALIZACIONES PENDIENTES:*\n"
                    message += "```\n" + "\n".join(upgradable_packages) + "\n```\n"
                    message += "Considera ejecutar `sudo apt upgrade`."
                    await bot_instance.send_message(super_admin_id, message, parse_mode='Markdown')
                    logging.info("Actualizaciones pendientes notificadas.")
                else:
                    logging.info("No hay actualizaciones pendientes.")
                
                config['monitoring_thresholds']['last_update_check'] = current_time
                guardar_configuracion(config)
            except Exception as e:
                logging.error(f"Error en periodic_update_check: {e}")
        
        # Pausar antes de la siguiente ronda de comprobaciones
        time.sleep(60) # Esperar 1 minuto antes de volver a chequear si ha pasado el intervalo


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
    application.add_handler(CommandHandler("dig", dig_command)) # NUEVO
    application.add_handler(CommandHandler("whois", whois_command)) # NUEVO

    # Comandos de monitoreo directo
    application.add_handler(CommandHandler("resources", resources_command)) # NUEVO
    application.add_handler(CommandHandler("disk", disk_command)) # NUEVO
    application.add_handler(CommandHandler("processes", processes_command)) # NUEVO
    application.add_handler(CommandHandler("systeminfo", systeminfo_command)) # NUEVO
    application.add_handler(CommandHandler("logs", logs_command)) # NUEVO
    application.add_handler(CommandHandler("docker", docker_command_handler)) # NUEVO
    application.add_handler(CommandHandler("updates", updates_command)) # NUEVO

    # NUEVOS MANEJADORES DE AYUDA Y USUARIOS
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("adduser", adduser_command))
    application.add_handler(CommandHandler("deluser", deluser_command))

    # Otros manejadores
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file_upload))
    application.add_handler(CommandHandler("get", get_file))

    # Iniciar el hilo para las comprobaciones periódicas
    monitor_thread = threading.Thread(target=lambda: application.run_until_idle(periodic_checks(application)))
    monitor_thread.daemon = True # Asegura que el hilo se cierre cuando el programa principal termine
    monitor_thread.start()

    logging.info("El bot se ha iniciado y está escuchando...")
    # application.run_polling() es bloqueante, periodic_checks necesita ejecutarse en segundo plano
    # Usamos run_polling en el hilo principal y el monitor en otro.
    application.run_polling(poll_interval=3) # Poll cada 3 segundos


if __name__ == "__main__":
    main()
