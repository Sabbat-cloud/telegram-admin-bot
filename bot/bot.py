# -----------------------------------------------------------------------------
# Bot de Telegram para Administración de Sistemas
#
# Autor: [Oscar Gimenez Blasco Sabbat.cloud]
# Versión: 1.0.0
# Descripción: Un bot multifuncional para monitorizar, administrar y
#              realizar diagnósticos de red en sistemas Linux.
# -----------------------------------------------------------------------------

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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot.log',  # Fichero de log estándar
    filemode='a'
)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(console_handler)

# --- CONSTANTES Y CONFIGURACIÓN GLOBAL ---
CONFIG_FILE = 'config.json'

# --- DECORADOR Y FUNCIONES DE UTILIDAD ---
def authorized_only(func):
    """Decorador para restringir el acceso solo a usuarios autorizados en el config."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        # Se asume que la configuración ya está cargada en context.bot_data
        authorized_users = context.bot_data.get('config', {}).get("telegram", {}).get("authorized_users", [])
        if user_id not in authorized_users:
            logging.warning(f"Acceso no autorizado denegado para el usuario con ID: {user_id}")
            if update.callback_query:
                await update.callback_query.answer("❌ No tienes permiso.", show_alert=True)
            else:
                await update.message.reply_text("❌ No tienes permiso para usar este bot.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def load_config():
    """Carga la configuración desde el fichero JSON."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.critical(f"FATAL: El archivo de configuración '{CONFIG_FILE}' no se encontró.")
        sys.exit("Error: Archivo de configuración no encontrado.")
    except json.JSONDecodeError:
        logging.critical(f"FATAL: El archivo '{CONFIG_FILE}' contiene un JSON inválido.")
        sys.exit("Error: Formato de configuración inválido.")

# --- MÓDULOS DE VERIFICACIÓN ---
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


# --- LÓGICA DE COMANDOS ---
def get_resources_text():
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
            f"--- **CPU** ---\nUso actual: `{cpu_percent}%`\n{load_avg_text}\n"
            f"--- **Memoria (RAM)** ---\nUso: `{ram_used}` de `{ram_total}` (*{ram_percent}%*)\n\n"
            f"--- **Disco Principal (/)** ---\nUso: `{disk_used}` de `{disk_total}` (*{disk_percent}%*)"
        )
    except Exception as e:
        logging.error(f"Error al obtener recursos con psutil: {e}")
        return f"❌ **Error inesperado al obtener recursos:** {e}"

def get_status_report_text(config):
    reporte_data = {}
    for servidor in config.get("servidores", []):
        nombre_servidor, host = servidor.get("nombre"), servidor.get("host")
        if not host: continue
        reporte_data[nombre_servidor] = []
        if "ping" in servidor.get("chequeos", {}):
            reporte_data[nombre_servidor].append(check_ping(host))
        if "puertos" in servidor.get("chequeos", {}):
            for p_name, p_num in servidor["chequeos"]["puertos"].items():
                reporte_data[nombre_servidor].append(check_port(host, p_name, p_num))
        if "certificado_ssl" in servidor.get("chequeos", {}):
            params = servidor["chequeos"]["certificado_ssl"]
            reporte_data[nombre_servidor].append(check_ssl_expiry(host, params.get("puerto", 443), params.get("dias_aviso", 30)))
    encabezado = f"📋 **Reporte de Estado (desde {platform.node()})**\n"
    lineas_reporte = [encabezado]
    for servidor, checks in reporte_data.items():
        lineas_reporte.append(f"\n--- **{servidor}** ---")
        lineas_reporte.extend(checks)
    lineas_reporte.append(f"\n_{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
    return "\n".join(lineas_reporte)

# --- FUNCIONES DE RED ---
def do_ping(host: str) -> str:
    try:
        param = '-n 4' if platform.system().lower() == 'windows' else '-c 4'
        proc = subprocess.run(['ping', param, host], capture_output=True, text=True, timeout=20)
        return f"📡 **Resultado de Ping a `{host}`:**\n```\n{proc.stdout or proc.stderr}\n```"
    except FileNotFoundError: return "❌ Error: El comando `ping` no se encuentra."
    except subprocess.TimeoutExpired: return f"❌ Error: Timeout (20s) haciendo ping a `{host}`."
    except Exception as e: return f"❌ Error inesperado: {e}"

def do_traceroute(host: str) -> str:
    try:
        proc = subprocess.run(['traceroute', '-w', '2', host], capture_output=True, text=True, timeout=60)
        return f"🗺️ **Resultado de Traceroute a `{host}`:**\n```\n{proc.stdout or proc.stderr}\n```"
    except FileNotFoundError: return "❌ Error: `traceroute` no se encuentra. ¿Está instalado?"
    except subprocess.TimeoutExpired: return f"❌ Error: Timeout (60s) durante el traceroute."
    except Exception as e: return f"❌ Error inesperado: {e}"

def do_nmap(host: str) -> str:
    try:
        proc = subprocess.run(['nmap', '-A', host], capture_output=True, text=True, timeout=600)
        output = proc.stdout or proc.stderr
        if len(output) > 4000: output = output[:4000] + "\n\n... (salida truncada)"
        return f"🔬 **Resultado de Nmap -A a `{host}`:**\n```\n{output}\n```"
    except FileNotFoundError: return "❌ Error: `nmap` no se encuentra. ¿Está instalado?"
    except subprocess.TimeoutExpired: return f"❌ Error: Timeout (10 min) durante el escaneo nmap."
    except Exception as e: return f"❌ Error inesperado: {e}"

# --- MENÚS ---
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Monitorización", callback_data='menu:monitor')],
        [InlineKeyboardButton("⚙️ Administración", callback_data='menu:admin')],
        [InlineKeyboardButton("🛠️ Herramientas de Red", callback_data='menu:network_tools')],
        [InlineKeyboardButton("📁 Gestión de Archivos", callback_data='menu:files')],
        [InlineKeyboardButton("🔄 Actualizar", callback_data='refresh_main')]
    ])

# ... (El resto de funciones de menús como monitor_menu_keyboard, etc., son iguales)
def monitor_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Sistemas (Status General)", callback_data='monitor:status_all')],
        [InlineKeyboardButton("Recursos Locales (CPU/RAM)", callback_data='monitor:resources')],
        [InlineKeyboardButton("Estado de un Servicio", callback_data='menu:services')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='menu:main')]
    ])

def admin_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Ejecutar Script Shell", callback_data='menu:run_script_shell')],
        [InlineKeyboardButton("🐍 Ejecutar Script Python", callback_data='menu:run_script_python')],
        [InlineKeyboardButton("🗓️ Ver Tareas Cron", callback_data='admin:check_cron')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='menu:main')]
    ])

def files_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🖼️ Listar Imágenes", callback_data='files:list_imagenes')],
        [InlineKeyboardButton("📄 Listar Ficheros", callback_data='files:list_ficheros')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='menu:main')]
    ])

def network_tools_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📡 Ping", callback_data='network:select_ping')],
        [InlineKeyboardButton("🗺️ Traceroute", callback_data='network:select_traceroute')],
        [InlineKeyboardButton("🔬 Escaneo Nmap (-A)", callback_data='network:select_nmap')],
        [InlineKeyboardButton("⬅️ Volver", callback_data='menu:main')]
    ])

def dynamic_host_keyboard(config: dict, action: str):
    keyboard = [[InlineKeyboardButton(f"🎯 {s['nombre']} ({s['host']})", callback_data=f"run:{action}:{s['host']}")]
                for s in config.get("servidores", []) if s.get("host") and s.get("nombre")]
    keyboard.append([InlineKeyboardButton("⬅️ Volver a Herramientas", callback_data='menu:network_tools')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_script_keyboard(config: dict, script_type: str):
    key = "scripts_permitidos" if script_type == 'shell' else "python_scripts_permitidos"
    prefix = "run:shell:" if script_type == 'shell' else "run:python:"
    keyboard = [[InlineKeyboardButton(f"Ejecutar '{name}'", callback_data=f"{prefix}{name}")]
                for name in config.get(key, {})]
    keyboard.append([InlineKeyboardButton("⬅️ Volver a Admin", callback_data='menu:admin')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_services_keyboard(config: dict):
    keyboard = [[InlineKeyboardButton(f"Estado de '{service}'", callback_data=f"service:{service}")]
                for service in config.get("servicios_permitidos", [])]
    keyboard.append([InlineKeyboardButton("⬅️ Volver a Monitor", callback_data='menu:monitor')])
    return InlineKeyboardMarkup(keyboard)


# --- MANEJADORES DE COMANDOS Y BOTONES ---
@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"¡Hola {user.first_name}! 👋", reply_markup=main_menu_keyboard())

@authorized_only
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    config = context.bot_data.get('config')

    # Menús principales
    if data == 'menu:main': await query.edit_message_text("Menú Principal", reply_markup=main_menu_keyboard())
    elif data == 'menu:monitor': await query.edit_message_text("Menú de Monitorización", reply_markup=monitor_menu_keyboard())
    elif data == 'menu:admin': await query.edit_message_text("Menú de Administración", reply_markup=admin_menu_keyboard())
    elif data == 'menu:files': await query.edit_message_text("Menú de Archivos", reply_markup=files_menu_keyboard())
    elif data == 'menu:network_tools': await query.edit_message_text("Herramientas de Red", reply_markup=network_tools_menu_keyboard())

    # Monitorización
    elif data == 'monitor:status_all':
        await query.edit_message_text("🔍 Obteniendo estado...", parse_mode='Markdown')
        await query.edit_message_text(get_status_report_text(config), parse_mode='Markdown', reply_markup=monitor_menu_keyboard())
    elif data == 'monitor:resources':
        await query.edit_message_text(get_resources_text(), parse_mode='Markdown', reply_markup=monitor_menu_keyboard())
    elif data == 'menu:services':
        await query.edit_message_text("Selecciona un servicio:", reply_markup=dynamic_services_keyboard(config))

    # Herramientas de Red
    elif data.startswith('network:select_'):
        tool = data.split('_')[1]
        text_map = {'ping': '📡 Ping', 'traceroute': '🗺️ Traceroute', 'nmap': '🔬 Escaneo Nmap'}
        texto = f"{text_map[tool]}\n\nSelecciona un objetivo o usa `/{tool} <host>`."
        await query.edit_message_text(texto, parse_mode='Markdown', reply_markup=dynamic_host_keyboard(config, tool))
    elif data.startswith('run:ping:') or data.startswith('run:traceroute:') or data.startswith('run:nmap:'):
        tool, host = data.split(':')[1], data.split(':', 2)[2]
        tool_map = {'ping': do_ping, 'traceroute': do_traceroute, 'nmap': do_nmap}
        await query.edit_message_text(f"Ejecutando `{tool}` en `{host}`...", parse_mode='Markdown')
        result = tool_map[tool](host)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_host_keyboard(config, tool))

    # ... (El resto de la lógica de botones es similar y puede seguir aquí)


# --- MANEJADOR DE COMANDOS DE RED (REFACTORIZADO) ---
async def _handle_network_command(update: Update, context: ContextTypes.DEFAULT_TYPE, tool_func, usage: str, message: str):
    if not context.args:
        await update.message.reply_text(f"Uso: {usage}")
        return
    host = context.args[0]
    # Aquí se podría añadir una validación de seguridad para el 'host'
    await update.message.reply_text(f"{message} `{host}`...", parse_mode='Markdown')
    result = tool_func(host)
    await update.message.reply_text(result, parse_mode='Markdown')

@authorized_only
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_network_command(update, context, do_ping, "/ping <host>", "📡 Haciendo ping a")
@authorized_only
async def traceroute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_network_command(update, context, do_traceroute, "/traceroute <host>", "🗺️ Ejecutando traceroute a")
@authorized_only
async def nmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_network_command(update, context, do_nmap, "/nmap <host>", "🔬 Ejecutando escaneo Nmap a")

# --- MANEJADORES DE ARCHIVOS ---
# ... (Las funciones handle_file_upload y get_file son iguales)
# (Se omiten por brevedad, pero deben estar en el fichero final)

# --- MOTOR PRINCIPAL DEL BOT ---
def main():
    """Función principal que inicia el bot."""
    config = load_config()
    token = config.get("telegram", {}).get("token")
    if not token or token == "AQUI_VA_EL_TOKEN_DEL_BOT":
        logging.critical("El token de Telegram no está configurado en config.json.")
        sys.exit("Error: Token de Telegram no configurado.")

    app = Application.builder().token(token).build()
    
    # Carga la configuración en el contexto del bot para acceso global
    app.bot_data['config'] = config

    # Registro de Manejadores
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_callback_handler))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("traceroute", traceroute_command))
    app.add_handler(CommandHandler("nmap", nmap_command))
    # app.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file_upload))
    # app.add_handler(CommandHandler("get", get_file))

    logging.info("El bot se ha iniciado correctamente.")
    app.run_polling()

if __name__ == "__main__":
    main()
