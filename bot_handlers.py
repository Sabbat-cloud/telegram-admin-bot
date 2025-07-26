# bot_handlers.py
# Todos los manejadores.

import logging
import os
import re
import ipaddress
import subprocess
import sys
import time
import datetime
import asyncio
from functools import wraps

from telegram.ext import ContextTypes, ConversationHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown

from core_functions import *
from localization import setup_translation, get_system_translator

# --- AÑADIDO: Lock para tareas pesadas para evitar DoS ---
HEAVY_TASK_LOCK = asyncio.Lock()

# --- Definición de estados para la conversación ---
AWAITING_LOCATION = 1

# --- Decoradores ---
def authorized_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        _ = setup_translation(context)
        user_id = update.effective_user.id

        # --- INICIO DE MODIFICACIÓN DE DIAGNÓSTICO ---
        logging.info(f"[AUTH_CHECK] Iniciando comprobación para el usuario ID: {user_id}")

        users_config = cargar_usuarios()
        authorized_list = users_config.get("authorized_users", [])

        logging.info(f"[AUTH_CHECK] Lista de usuarios autorizados cargada: {authorized_list}")
        # --- FIN DE MODIFICACIÓN DE DIAGNÓSTICO ---

        if user_id not in authorized_list:
            logging.warning(f"[AUTH_CHECK] ACCESO DENEGADO para el usuario ID: {user_id}. No está en la lista.") # Modificamos este log también
            if update.callback_query:
                await update.callback_query.answer(_("❌ No tienes permiso."), show_alert=True)
            else:
                await update.message.reply_text(_("❌ No tienes permiso para usar este bot."))
            return

        logging.info(f"[AUTH_CHECK] ACCESO PERMITIDO para el usuario ID: {user_id}")
        return await func(update, context, *args, **kwargs)
    return wrapped
def super_admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        _ = setup_translation(context)
        user_id = update.effective_user.id
        users_config = cargar_usuarios()
        if user_id != users_config.get("super_admin_id"):
            logging.warning(f"Intento de ejecución de comando de super admin por usuario no autorizado: {user_id}")
            await update.message.reply_text(_("⛔ Este comando solo puede ser usado por el super administrador."))
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- DECORADOR ANTI-FLOOD Y DE-DUPLICACIÓN ---
def rate_limit_and_deduplicate(limit_seconds: int = 5):
    """
    Decorador para prevenir el flood. Ignora un comando si es idéntico al
    anterior del mismo usuario y se envía dentro del límite de tiempo.
    """
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.message:
                return await func(update, context, *args, **kwargs)

            user_id = update.effective_user.id
            current_time = time.time()
            message_text = update.message.text

            last_message = context.user_data.get('last_message', {})
            last_text = last_message.get('text')
            last_time = last_message.get('time', 0)

            if message_text and message_text == last_text and (current_time - last_time) < limit_seconds:
                logging.warning(f"Mensaje duplicado bloqueado para el usuario {user_id}: '{message_text}'")
                return

            context.user_data['last_message'] = {'text': message_text, 'time': current_time}

            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator

# --- AÑADIDO: Función de validación de entradas ---
def is_safe_grep_pattern(pattern: str) -> bool:
    """
    Valida que un patrón de búsqueda para grep sea razonablemente seguro,
    evitando metacaracteres de expresiones regulares muy complejos o peligrosos.
    """
    if not pattern:
        return False

    # Lista negra de caracteres o secuencias peligrosas que pueden causar un "ReDoS" (Regular Expression Denial of Service)
    # o que simplemente no son necesarios para un uso normal.
    # Ej: backreferences, lookarounds, etc.
    blacklist = ['\\', '(', ')', '[', ']', '{', '}', '+', '*', '?', '^', '$']
    
    # Permitimos un conjunto básico de caracteres alfanuméricos y algunos símbolos seguros.
    # Esta es una lista blanca.
    whitelist_pattern = re.compile(r"^[a-zA-Z0-9\s\._\-:\",'/=]+$")

    if not whitelist_pattern.fullmatch(pattern):
        logging.warning(f"Patrón de búsqueda bloqueado por la lista blanca: {pattern}")
        return False
    
    return True


def is_valid_target(target: str) -> bool:
    """
    Valida de forma estricta que el 'target' sea una dirección IP válida (IPv4/IPv6)
    o un nombre de host compatible con RFC 1123.
    """
    if not target or len(target) > 255:
        return False

    # 1. Validar si es una dirección IP
    try:
        ipaddress.ip_address(target)
        # Si no lanza excepción, es una IP válida.
        return True
    except ValueError:
        # No es una IP, continuamos para ver si es un hostname.
        pass

    # 2. Validar si es un nombre de host (hostname) según RFC 1123
    # Un hostname no puede empezar o terminar con un guion.
    if target.startswith('-') or target.endswith('-'):
        return False
    
    # Expresión regular estricta para hostnames.
    # Permite letras, números, guiones y puntos.
    hostname_pattern = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$")
    
    if hostname_pattern.fullmatch(target):
        return True

    return False
# --- Teclados---
def main_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("📊 Monitorización"), callback_data='menu:monitor')],
        [InlineKeyboardButton(_("⚙️ Administración"), callback_data='menu:admin')],
        [InlineKeyboardButton(_("🛠️ Herramientas de Red"), callback_data='menu:network_tools')],
        [InlineKeyboardButton(_("🔧 Utilidades"), callback_data='menu:utils')],
        [InlineKeyboardButton(_("🐳 Gestión Docker"), callback_data='menu:docker')],
        [InlineKeyboardButton(_("📦 Gestión de Backups"), callback_data='menu:backups')],
        [InlineKeyboardButton(_("📁 Gestión de Archivos"), callback_data='menu:files')],
        [InlineKeyboardButton(_("🌐 Idioma / Language"), callback_data='menu:language')],
        [InlineKeyboardButton(_("❓ Ayuda"), callback_data='menu:help')],
        [InlineKeyboardButton(_("🍀 Fortuna"), callback_data='menu:fortune')],
        [InlineKeyboardButton(_("🔄 Actualizar"), callback_data='refresh_main')]
    ])

def monitor_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("Sistemas (Status General)"), callback_data='monitor:status_all')],
        [InlineKeyboardButton(_("Recursos Locales (CPU/RAM)"), callback_data='monitor:resources')],
        [InlineKeyboardButton(_("Uso de Disco (`df -h`)"), callback_data='monitor:disk')],
        [InlineKeyboardButton(_("Info. Sistema (`uname -a`)"), callback_data='monitor:systeminfo')],
        [InlineKeyboardButton(_("Ver Logs"), callback_data='menu:logs')],
        [InlineKeyboardButton(_("🔎 Estado de un Servicio"), callback_data='menu:services_status')],
        [InlineKeyboardButton(_("▶️ Iniciar Servicio"), callback_data='menu:services_start')],
        [InlineKeyboardButton(_("⏹️ Parar Servicio"), callback_data='menu:services_stop')],
        [InlineKeyboardButton(_("🔄 Reiniciar Servicio"), callback_data='menu:services_restart')],
        [InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')]
    ])

def admin_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("▶️ Ejecutar Script Shell"), callback_data='menu:run_script_shell')],
        [InlineKeyboardButton(_("🐍 Ejecutar Script Python"), callback_data='menu:run_script_python')],
        [InlineKeyboardButton(_("🗓️ Ver Tareas Cron"), callback_data='admin:check_cron')],
        [InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')]
    ])

def files_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("🖼️ Listar Imágenes"), callback_data='files:list_imagenes')],
        [InlineKeyboardButton(_("📄 Listar Ficheros"), callback_data='files:list_ficheros')],
        [InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')]
    ])

def network_tools_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("📡 Ping"), callback_data='network:select_ping')],
        [InlineKeyboardButton(_("🗺️ Traceroute"), callback_data='network:select_traceroute')],
        [InlineKeyboardButton(_("🔬 Escaneo Nmap (-A)"), callback_data='network:select_nmap')],
        [InlineKeyboardButton(_("🌐 Dig (DNS Lookup)"), callback_data='network:select_dig')],
        [InlineKeyboardButton(_("👤 Whois"), callback_data='network:select_whois')],
        [InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')]
    ])

def utilities_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("🌦️ Consultar Tiempo"), callback_data='weather:start')],
        [InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')]
    ])

def backups_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("▶️ Ejecutar un Backup"), callback_data='backups:list')],
        [InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')]
    ])

def dynamic_backup_script_keyboard(_):
    scripts = cargar_configuracion().get("backup_scripts", {})
    keyboard = []
    if not scripts:
        keyboard.append([InlineKeyboardButton(_("No hay scripts de backup definidos"), callback_data='no_op')])
    else:
        for name in scripts:
            keyboard.append([InlineKeyboardButton(f"🚀 {name}", callback_data=f"backup:run:{name}")])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Backups"), callback_data='menu:backups')])
    return InlineKeyboardMarkup(keyboard)

def language_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Español 🇪🇸", callback_data='set_lang:es')],
        [InlineKeyboardButton("English 🇬🇧", callback_data='set_lang:en')],
        [InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')]
    ])

def dynamic_host_keyboard(action: str, _):
    hosts = cargar_configuracion().get("servidores", [])
    keyboard = []
    for server in hosts:
        if server.get("host"):
            keyboard.append([InlineKeyboardButton(f'🎯 {server.get("nombre")}', callback_data=f"run:{action}:{server.get('host')}")])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Herramientas"), callback_data='menu:network_tools')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_script_keyboard(script_type, _):
    key = "scripts_permitidos" if script_type == 'shell' else "python_scripts_permitidos"
    prefix = "run:shell:" if script_type == 'shell' else "run:python:"
    scripts = cargar_configuracion().get(key, {})
    keyboard = []
    for name in scripts:
        keyboard.append([InlineKeyboardButton(_("Ejecutar '{name}'").format(name=name), callback_data=f"{prefix}{name}")])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Admin"), callback_data='menu:admin')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_services_action_keyboard(action: str, _):
    services = cargar_configuracion().get("servicios_permitidos", [])
    keyboard = []
    action_icon_map = {'status': '🔎', 'start': '▶️', 'stop': '⏹️', 'restart': '🔄'}
    icon = action_icon_map.get(action, '⚙️')
    for service in services:
        keyboard.append([InlineKeyboardButton(f"{icon} {service}", callback_data=f"service:{action}:{service}")])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Monitor"), callback_data='menu:monitor')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_logs_keyboard(_):
    logs = cargar_configuracion().get("allowed_logs", {})
    keyboard = []
    for alias in logs.keys():
        keyboard.append([InlineKeyboardButton(_("Ver '{alias}'").format(alias=alias), callback_data=f"log:view:{alias}")])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Monitor"), callback_data='menu:monitor')])
    return InlineKeyboardMarkup(keyboard)

def docker_menu_keyboard(_):
    containers = cargar_configuracion().get("docker_containers_allowed", [])
    keyboard = [[InlineKeyboardButton(_("Listar Contenedores (`docker ps`)"), callback_data='docker:ps')]]
    if containers:
        keyboard.append([InlineKeyboardButton(_("Ver Logs de Contenedor"), callback_data='docker:select_logs')])
        keyboard.append([InlineKeyboardButton(_("Reiniciar Contenedor"), callback_data='docker:select_restart')])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_docker_container_keyboard(action: str, _):
    containers = cargar_configuracion().get("docker_containers_allowed", [])
    keyboard = []
    for container in containers:
        keyboard.append([InlineKeyboardButton(_("{action} '{container}'").format(action=action.capitalize(), container=container), callback_data=f"docker:{action}:{container}")])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Docker"), callback_data='menu:docker')])
    return InlineKeyboardMarkup(keyboard)


# --- Comandos Principales ---

@authorized_only
@rate_limit_and_deduplicate()
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    user = update.effective_user
    await update.message.reply_text(
        _("¡Hola {first_name}! 👋\n\nSelecciona una opción del menú para empezar.").format(first_name=user.first_name),
        reply_markup=main_menu_keyboard(_)
    )

@authorized_only
@rate_limit_and_deduplicate()
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await update.message.reply_text(get_help_text(_), parse_mode='Markdown')

@authorized_only
@rate_limit_and_deduplicate()
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await update.message.reply_text(
        _("Selecciona tu idioma:"),
        reply_markup=language_menu_keyboard(_)
    )

@authorized_only
@rate_limit_and_deduplicate()
async def fortune_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    thinking_message = await update.message.reply_text("🍀...")
    fortune_text = await asyncio.to_thread(get_fortune_text, _)
    await thinking_message.edit_text(fortune_text, parse_mode='Markdown')

# --- Manejador de Botones ---
@authorized_only
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith('set_lang:'):
        lang_code = data.split(':')[1]
        context.user_data['lang'] = lang_code
        _ = setup_translation(context)
        lang_name = 'Español' if lang_code == 'es' else 'English'
        await query.edit_message_text(
            _("Idioma actualizado a {lang_name}.").format(lang_name=lang_name),
            reply_markup=main_menu_keyboard(_)
        )
        return

    menu_map = {
        'menu:main': (_("Menú Principal"), main_menu_keyboard),
        'menu:monitor': (_("Menú de Monitorización"), monitor_menu_keyboard),
        'menu:admin': (_("Menú de Administración"), admin_menu_keyboard),
        'menu:backups': (_("📦 Gestión de Backups"), backups_menu_keyboard),
        'backups:list': (_("Selecciona el backup a ejecutar:"), dynamic_backup_script_keyboard),
        'menu:utils': (_("🔧 Menú de Utilidades"), utilities_menu_keyboard),
        'menu:language': (_("Selecciona tu idioma:"), language_menu_keyboard),
        'menu:files': (_("Menú de Gestión de Archivos\n\nPara subir, simplemente envía el archivo."), files_menu_keyboard),
        'menu:network_tools': (_("🛠️ Herramientas de Red"), network_tools_menu_keyboard),
        'menu:docker': (_("🐳 Gestión Docker"), docker_menu_keyboard),
        'menu:logs': (_("Selecciona un log:"), dynamic_logs_keyboard),
        'menu:services_status': (_("Selecciona un servicio para ver su estado:"), lambda: dynamic_services_action_keyboard('status', _)),
        'menu:services_start': (_("Selecciona un servicio para INICIAR:"), lambda: dynamic_services_action_keyboard('start', _)),
        'menu:services_stop': (_("Selecciona un servicio para PARAR:"), lambda: dynamic_services_action_keyboard('stop', _)),
        'menu:services_restart': (_("Selecciona un servicio para REINICIAR:"), lambda: dynamic_services_action_keyboard('restart', _)),
        'menu:run_script_shell': (_("Selecciona script de Shell a ejecutar:"), lambda: dynamic_script_keyboard('shell', _)),
        'menu:run_script_python': (_("Selecciona script de Python a ejecutar:"), lambda: dynamic_script_keyboard('python', _)),
        'network:select_ping': (_("📡 **Ping**: Elige un objetivo"), lambda: dynamic_host_keyboard('ping', _)),
        'network:select_traceroute': (_("🗺️ **Traceroute**: Elige un objetivo"), lambda: dynamic_host_keyboard('traceroute', _)),
        'network:select_nmap': (_("🔬 **Nmap**: Elige un objetivo"), lambda: dynamic_host_keyboard('nmap', _)),
        'network:select_dig': (_("🌐 **Dig**: Elige un objetivo"), lambda: dynamic_host_keyboard('dig', _)),
        'network:select_whois': (_("👤 **Whois**: Elige un objetivo"), lambda: dynamic_host_keyboard('whois', _)),
        'docker:select_logs': (_("Selecciona contenedor para ver logs:"), lambda: dynamic_docker_container_keyboard('logs', _)),
        'docker:select_restart': (_("Selecciona contenedor para reiniciar:"), lambda: dynamic_docker_container_keyboard('restart', _)),
    }

    if data in menu_map:
        text, keyboard_item = menu_map[data]
        final_keyboard = keyboard_item(_) if 'lambda' not in repr(keyboard_item) else keyboard_item()
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=final_keyboard)
        return
    elif data == 'menu:help':
        await query.message.reply_text(get_help_text(_), parse_mode='Markdown')
        return
    elif data == 'menu:fortune':
        await query.edit_message_text("🍀...", parse_mode='Markdown')
        fortune_text = await asyncio.to_thread(get_fortune_text, _)
        await query.edit_message_text(fortune_text, parse_mode='Markdown', reply_markup=main_menu_keyboard(_))
        return
    if data == 'refresh_main':
        time_str = datetime.datetime.now().strftime('%H:%M:%S')
        await query.edit_message_text(_("Menú actualizado a las {time}").format(time=time_str), reply_markup=main_menu_keyboard(_))
        return

    parts = data.split(':', 2)
    action_type, action_name, param = parts[0], parts[1], (parts[2] if len(parts) > 2 else None)

    monitor_map = {
        'status_all': get_status_report_text, 'resources': get_resources_text,
        'disk': get_disk_usage_text, 'processes': get_processes_text, 'systeminfo': get_system_info_text,
    }

    if action_type == 'monitor' and action_name in monitor_map:
        await query.edit_message_text(_("Obteniendo {action_name}...").format(action_name=action_name.replace('_', ' ')))
        reporte = await asyncio.to_thread(monitor_map[action_name], _)
        await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard(_))

    elif action_type == 'run':
        tool_map = {'ping': do_ping, 'traceroute': do_traceroute, 'nmap': do_nmap, 'dig': do_dig, 'whois': do_whois}
        if action_name in tool_map:
            # --- MODIFICADO: Añadida validación de entrada ---
            if not is_valid_target(param):
                await query.edit_message_text(_("❌ El objetivo '{param}' no es válido.").format(param=param))
                return
            
            # --- MODIFICADO: Añadido control de concurrencia para tareas pesadas ---
            heavy_tasks = ['nmap', 'traceroute']
            if action_name in heavy_tasks:
                if HEAVY_TASK_LOCK.locked():
                    await query.answer(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."), show_alert=True)
                    return
                async with HEAVY_TASK_LOCK:
                    await query.edit_message_text(_("⏳ Ejecutando `{action}` en `{param}`... (Puede tardar)").format(action=action_name, param=param), parse_mode='Markdown')
                    result = await asyncio.to_thread(tool_map[action_name], param, _)
            else:
                await query.edit_message_text(_("⏳ Ejecutando `{action}` en `{param}`...").format(action=action_name, param=param), parse_mode='Markdown')
                result = await asyncio.to_thread(tool_map[action_name], param, _)
                
            await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_host_keyboard(action_name, _))

        elif action_name == 'shell':
            await query.edit_message_text(_("🚀 Ejecutando script de Shell '{param}'...").format(param=param), parse_mode='Markdown')
            salida = await asyncio.to_thread(run_shell_script, param, _)
            await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=dynamic_script_keyboard('shell', _))

        elif action_name == 'python':
            await query.edit_message_text(_("🐍 Ejecutando script de Python '{param}'...").format(param=param), parse_mode='Markdown')
            salida = await asyncio.to_thread(run_python_script, param, _)
            await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=dynamic_script_keyboard('python', _))

    elif action_type == 'docker':
        await query.edit_message_text(_("🐳 Procesando comando docker..."))
        result = await asyncio.to_thread(docker_command, action_name, _, param, num_lines=20)
        keyboard = docker_menu_keyboard(_) if action_name == 'ps' else dynamic_docker_container_keyboard(action_name, _)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=keyboard)

    elif action_type == 'log' and action_name == 'view':
        await query.edit_message_text(_("📜 Obteniendo últimas 20 líneas de `{param}`...").format(param=param), parse_mode='Markdown')
        result = await asyncio.to_thread(get_log_lines, param, 20, _)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_logs_keyboard(_))

    elif action_type == 'service':
        if param == 'telegram_bot' and action_name in ['stop', 'restart']:
            await query.edit_message_text(
                _("🛡️ **Acción denegada por seguridad.**\n\nNo se permite parar o reiniciar el propio servicio del bot desde aquí. "
                  "Por favor, hazlo desde la consola del servidor con `systemctl`."),
                parse_mode='Markdown',
                reply_markup=dynamic_services_action_keyboard(action_name, _)
            )
            return

        if action_name == 'status':
            await query.edit_message_text(_("🔎 Verificando estado de `{param}`...").format(param=param), parse_mode='Markdown')
            reporte = await asyncio.to_thread(get_service_status, param, _)
            await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=dynamic_services_action_keyboard('status', _))
        elif action_name in ['start', 'stop', 'restart']:
            action_text_map = {'start': _("Iniciando"), 'stop': _("Parando"), 'restart': _("Reiniciando")}
            await query.edit_message_text(_("⏳ {txt} servicio `{srv}`...").format(txt=action_text_map[action_name], srv=param), parse_mode='Markdown')
            result = await asyncio.to_thread(manage_service, param, action_name, _)
            await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_services_action_keyboard(action_name, _))

    elif action_type == 'files' and action_name.startswith('list_'):
        await query.edit_message_text(_("📁 Listando ficheros..."))
        folder_type = action_name.split('_')[1]
        folder_key = "image_directory" if folder_type == 'imagenes' else "file_directory"
        config = cargar_configuracion()
        target_dir = os.path.expanduser(config.get(folder_key, ''))
        if not target_dir or not os.path.isdir(target_dir):
            await query.edit_message_text(_("❌ La carpeta para `{type}` no está configurada o no existe.").format(type=folder_type), reply_markup=files_menu_keyboard(_)); return
        files = await asyncio.to_thread(os.listdir, target_dir)
        files_list = "\n".join(f"`{escape_markdown(f)}`" for f in files)
        message = _("ℹ️ La carpeta `{type}` está vacía.").format(type=folder_type) if not files else _("📁 **Archivos en `{type}`:**\n{lista}\n\nPara descargar, usa `/get {type} nombre_del_archivo`").format(type=folder_type, lista=files_list)
        await query.edit_message_text(message[:4090] + "..." if len(message) > 4096 else message, parse_mode='Markdown', reply_markup=files_menu_keyboard(_))

    elif action_type == 'admin' and action_name == 'check_cron':
        await query.edit_message_text(_("🗓️ Obteniendo tareas de Cron..."), parse_mode='Markdown')
        salida = await asyncio.to_thread(get_cron_tasks, _)
        await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=admin_menu_keyboard(_))

    # --- MODIFICADO: Añadido control de concurrencia para backups ---
    elif action_type == 'backup' and action_name == 'run':
        if HEAVY_TASK_LOCK.locked():
            await query.answer(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."), show_alert=True)
            return
        async with HEAVY_TASK_LOCK:
            await query.edit_message_text(_("⏳ Ejecutando backup '{script}'... (Puede tardar)").format(script=param), parse_mode='Markdown')
            resultado = await asyncio.to_thread(run_backup_script, param, _)
        await query.edit_message_text(resultado, parse_mode='Markdown', reply_markup=dynamic_backup_script_keyboard(_))


# --- Comandos (/comando) Refactorizados ---

async def _handle_async_command(update: Update, context: ContextTypes.DEFAULT_TYPE, func, thinking_msg: str):
    _ = setup_translation(context)
    message_to_edit = await update.message.reply_text(thinking_msg)
    result = await asyncio.to_thread(func, _)
    await message_to_edit.edit_text(result, parse_mode='Markdown')

async def _handle_async_network_command(update: Update, context: ContextTypes.DEFAULT_TYPE, func, usage: str, thinking_prefix: str, _):
    if not context.args:
        await update.message.reply_text(_("Uso: {use}").format(use=usage))
        return
    target = context.args[0]
    # --- MODIFICADO: Añadida validación de entrada ---
    if not is_valid_target(target):
        await update.message.reply_text(_("❌ El objetivo '{target}' no es válido.").format(target=target))
        return

    message_to_edit = await update.message.reply_text(f"{thinking_prefix} `{target}`...")
    result = await asyncio.to_thread(func, target, _)
    await message_to_edit.edit_text(result, parse_mode='Markdown')

@authorized_only
@rate_limit_and_deduplicate()
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_network_command(update, context, do_ping, "/ping <host>", _("📡 Haciendo ping a"), _)

# --- MODIFICADO: Añadido control de concurrencia ---
@authorized_only
@rate_limit_and_deduplicate()
async def traceroute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if HEAVY_TASK_LOCK.locked():
        await update.message.reply_text(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."))
        return
    async with HEAVY_TASK_LOCK:
        await _handle_async_network_command(update, context, do_traceroute, "/traceroute <host>", _("🗺️ Ejecutando traceroute a"), _)

# --- MODIFICADO: Añadido control de concurrencia ---
@authorized_only
@rate_limit_and_deduplicate()
async def nmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if HEAVY_TASK_LOCK.locked():
        await update.message.reply_text(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."))
        return
    async with HEAVY_TASK_LOCK:
        await _handle_async_network_command(update, context, do_nmap, "/nmap <host>", _("🔬 Ejecuturando Nmap a"), _)

@authorized_only
@rate_limit_and_deduplicate()
async def dig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_network_command(update, context, do_dig, "/dig <dominio>", _("🌐 Realizando consulta DIG para"), _)

@authorized_only
@rate_limit_and_deduplicate()
async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_network_command(update, context, do_whois, "/whois <dominio>", _("👤 Realizando consulta WHOIS para"), _)

@authorized_only
@rate_limit_and_deduplicate()
async def resources_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_async_command(update, context, get_resources_text, "💻 Obteniendo recursos...")

@authorized_only
@rate_limit_and_deduplicate()
async def disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_async_command(update, context, get_disk_usage_text, "💾 Obteniendo uso de disco...")

@authorized_only
@rate_limit_and_deduplicate()
async def processes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_async_command(update, context, get_processes_text, "⚙️ Listando procesos...")

@authorized_only
@rate_limit_and_deduplicate()
async def systeminfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _handle_async_command(update, context, get_system_info_text, "ℹ️ Obteniendo información del sistema...")

# --- MODIFICADO: Añadido control de concurrencia usando la nueva funcion sanitizadora-
@authorized_only
@rate_limit_and_deduplicate()
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    # ... (código existente) ...

    if context.args[0] == 'search':
        if len(context.args) < 3:
            await update.message.reply_text(_("Uso: `/logs search <alias> <patrón>`"), parse_mode='Markdown'); return
        
        # << INICIO DE LA MODIFICACIÓN >>
        alias_log = context.args[1]
        search_pattern = " ".join(context.args[2:])

        if not is_safe_grep_pattern(search_pattern):
            await update.message.reply_text(_("❌ El patrón de búsqueda contiene caracteres no permitidos o potencialmente peligrosos."))
            return
        # << FIN DE LA MODIFICACIÓN >>

        if HEAVY_TASK_LOCK.locked():
            await update.message.reply_text(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."))
            return
        async with HEAVY_TASK_LOCK:
            thinking_message = await update.message.reply_text("📜 Buscando en logs... (Puede tardar)")
            # Pasamos el alias y el patrón seguros a la función de búsqueda
            result = await asyncio.to_thread(search_log, alias_log, search_pattern, _) 
    else:
        # ... (resto del código sin cambios) ...
        pass
    
    await thinking_message.edit_text(result, parse_mode='Markdown')
@authorized_only
@rate_limit_and_deduplicate()
async def docker_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args:
        await update.message.reply_text(_("Uso: `/docker <ps|logs|restart> [contenedor] [líneas]`")); return

    thinking_message = await update.message.reply_text("🐳 Procesando comando docker...")
    action, container, lines = context.args[0], (context.args[1] if len(context.args) > 1 else None), (int(context.args[2]) if len(context.args) > 2 and context.args[2].isdigit() else 20)
    result = await asyncio.to_thread(docker_command, action, _, container, lines)
    await thinking_message.edit_text(result, parse_mode='Markdown')

@authorized_only
@rate_limit_and_deduplicate(limit_seconds=10) # Mayor tiempo para evitar envíos múltiples
async def receive_weather_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = setup_translation(context)
    location = update.message.text
    thinking_message = await update.message.reply_text(f"🌦️ {_('Consultando el tiempo para')} `{location}`...")
    weather_report = await asyncio.to_thread(get_weather_text, location, _)
    #await thinking_message.edit_text(weather_report, parse_mode='Markdown')
    await thinking_message.edit_text(
            weather_report, 
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard(_)
    )
    return ConversationHandler.END

# --- Comandos de IA (No bloqueantes) ---
@authorized_only
@rate_limit_and_deduplicate()
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    model_name = cargar_configuracion().get("gemini_api", {}).get("flash_model")
    if not model_name: await update.message.reply_text(_("❌ El modelo 'flash' no está configurado.")); return
    if not context.args: await update.message.reply_text(_("Uso: /ask <tu pregunta>\n(Modelo: {model})").format(model=model_name)); return

    thinking_message = await update.message.reply_text(_("🤔 Pensando con Gemini Flash..."))
    result = await asyncio.to_thread(ask_gemini_model, " ".join(context.args), model_name, _)
    await thinking_message.edit_text(result, parse_mode='Markdown')

@super_admin_only
@rate_limit_and_deduplicate()
async def askpro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    model_name = cargar_configuracion().get("gemini_api", {}).get("pro_model")
    if not model_name: await update.message.reply_text(_("❌ El modelo 'pro' no está configurado.")); return
    if not context.args: await update.message.reply_text(_("Uso: /askpro <pregunta compleja>\n(Modelo: {model})").format(model=model_name)); return

    thinking_message = await update.message.reply_text(_("🧠 Pensando con Gemini Pro... (puede tardar)"))
    result = await asyncio.to_thread(ask_gemini_model, " ".join(context.args), model_name, _)
    await thinking_message.edit_text(result, parse_mode='Markdown')

@authorized_only
@rate_limit_and_deduplicate()
async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    model_name = cargar_configuracion().get("gemini_api", {}).get("flash_model")
    if not model_name: await update.message.reply_text(_("❌ El modelo 'flash' no está configurado.")); return
    if len(context.args) < 2: await update.message.reply_text(_("Uso: /analyze <recurso> <pregunta...>\nRecursos: `status`, `resources`, `processes`, `disk`")); return

    resource, question = context.args[0].lower(), " ".join(context.args[1:])
    thinking_message = await update.message.reply_text(_("📊 Obteniendo datos para el análisis..."))

    source_data_map = {"status": get_status_report_text, "resources": get_resources_text, "processes": get_processes_text, "disk": get_disk_usage_text}
    if resource not in source_data_map:
        await thinking_message.edit_text(_("❌ Recurso no válido.")); return

    source_data = await asyncio.to_thread(source_data_map[resource], _)

    await thinking_message.edit_text(_("🧠 Analizando datos con Gemini flash..."))
    final_prompt = f"Eres un experto SRE con 20 años de experiencia. Analiza los siguientes datos de un servidor Linux y responde a la pregunta del usuario de forma clara y concisa, ofreciendo recomendaciones.\n\n--- DATOS ---\n{source_data}\n\n--- PREGUNTA ---\n{question}"
    result = await asyncio.to_thread(ask_gemini_model, final_prompt, model_name, _)
    await thinking_message.edit_text(result, parse_mode='Markdown')

# --- Fail2Ban ---
@super_admin_only
@rate_limit_and_deduplicate()
async def fail2ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args:
        await update.message.reply_text(_("Uso: `/fail2ban <status|unban> [IP]`"))
        return
    
    # --- MODIFICADO: Añadida validación de entrada para la IP ---
    subcommand = context.args[0].lower()
    if subcommand == 'unban':
        if len(context.args) < 2:
            await update.message.reply_text(_("Uso: `/fail2ban unban <IP>`"))
            return
        ip_address = context.args[1]
        # Una validación simple para IPs
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_address):
            await update.message.reply_text(_("❌ Formato de IP no válido."))
            return

    thinking_message = await update.message.reply_text(_("🛡️ Procesando comando Fail2Ban..."))

    if subcommand == 'status':
        result = await asyncio.to_thread(fail2ban_status, _)
        await thinking_message.edit_text(result, parse_mode='Markdown')
    elif subcommand == 'unban':
        ip_address = context.args[1]
        result = await asyncio.to_thread(fail2ban_unban, ip_address, _)
        await thinking_message.edit_text(result, parse_mode='Markdown')
    else:
        await thinking_message.edit_text(_("Comando no reconocido. Usa `status` o `unban`."))

# --- Tareas Periódicas ---
async def periodic_log_check(context: ContextTypes.DEFAULT_TYPE):
    _ = get_system_translator()
    logging.info("Ejecutando comprobación de monitorización de logs...")

    alerts = await asyncio.to_thread(check_watched_logs, _)

    if alerts:
        users_config = cargar_usuarios()
        super_admin_id = users_config.get("super_admin_id")
        if super_admin_id:
            for alert in alerts:
                try:
                    await context.bot.send_message(chat_id=super_admin_id, text=alert, parse_mode='Markdown')
                    await asyncio.sleep(1)
                except Exception as e:
                    logging.error(f"No se pudo enviar la alerta de log al super_admin: {e}")

# ---MUESTRA LA AYUDA ---

def get_help_text(_):
    return (
        _("🤖 **Ayuda Completa del Bot**\n\n"
          "--- **Comandos Generales** ---\n"
          "**/start**: Muestra el menú principal.\n"
          "**/help**: Muestra esta ayuda.\n"
          "**/language**: Cambia el idioma.\n"
          "**/fortune**: Muestra una galleta de la fortuna.\n\n"
          "--- **Inteligencia Artificial (Gemini)** ---\n"
          "**/ask** `<pregunta>`: Consulta a la IA (rápido).\n"
          "**/analyze** `<recurso> <pregunta>`: Pide a la IA que analice datos del sistema. Recursos: `status`, `resources`, `processes`, `disk`.\n\n"
          "--- **Monitorización** ---\n"
          "**/resources**: Reporte de CPU, RAM y carga.\n"
          "**/disk**: Uso de discos (`df -h`).\n"
          "**/processes**: Lista de procesos (`ps aux`).\n"
          "**/systeminfo**: Info del sistema.\n"
          "**/logs** `<alias> [líneas]`: Muestra las últimas líneas de un log.\n"
          "**/logs** `search <alias> <patrón>`: Busca en un log.\n\n"
          "--- **Gestión y Administración** ---\n"
          "**/docker** `<ps|logs|restart> [contenedor]`: Gestiona Docker.\n"
          "**/get** `<imagenes|ficheros> <fichero>`: Descarga un archivo.\n\n"
          "--- **Herramientas de Red** ---\n"
          "**/ping**, **/traceroute**, **/nmap**, **/dig**, **/whois** `<objetivo>`\n\n"
          "--- **Recordatorios** ---\n"
          "**/remind** `\"texto\" in <tiempo>`: Programa un recordatorio.\n"
          "**/reminders**: Lista tus recordatorios.\n"
          "**/delremind** `<ID>`: Borra un recordatorio.\n\n"
          "--- **Seguridad (Solo Super Admin)** ---\n"
          "**/fail2ban** `status`: Muestra el estado de las jaulas de Fail2Ban.\n"
          "**/fail2ban** `unban <IP>`: Desbloquea una IP.\n\n"
          "--- **Solo Super Admin** ---\n"
          "**/askpro** `<pregunta>`: Consulta a la IA (avanzado).\n"
          "**/adduser** `<user_id>`: Autoriza a un usuario.\n"
          "**/deluser** `<user_id>`: Revoca el acceso.\n"
          "**/listusers**: Lista usuarios autorizados.")
    )

async def reminder_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = setup_translation(context)
    job = context.job
    await context.bot.send_message(chat_id=job.chat_id, text=_("🔔 **Recordatorio:**\n\n{data}").format(data=job.data))

@authorized_only
@rate_limit_and_deduplicate()
async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    match = re.match(r'^\s*/remind\s+"([^"]+)"\s+(?:en|in)\s+(.+)$', update.message.text, re.IGNORECASE)
    if not match: await update.message.reply_text(_('Formato: `/remind "Texto" en 1d 2h 30m`'), parse_mode='Markdown'); return
    reminder_text, time_str, delay_seconds = match.group(1), match.group(2), parse_time_to_seconds(match.group(2))
    if delay_seconds <= 0: await update.message.reply_text(_("Duración inválida.")); return
    job_name = f"reminder_{update.effective_chat.id}_{int(time.time())}"
    context.job_queue.run_once(reminder_callback, delay_seconds, data=reminder_text, chat_id=update.effective_chat.id, name=job_name)
    await update.message.reply_text(_("✅ Recordatorio programado para *{txt}* en *{t}*.\nID: `{id}`").format(txt=reminder_text, t=time_str, id=job_name), parse_mode='Markdown')

@authorized_only
@rate_limit_and_deduplicate()
async def reminders_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    active_jobs = [j for j in context.job_queue.jobs() if j.name and j.name.startswith(f"reminder_{update.effective_chat.id}_")]
    if not active_jobs: await update.message.reply_text(_("ℹ️ No hay recordatorios programados.")); return
    message = _("🗓️ **Recordatorios Pendientes:**\n\n")
    for job in active_jobs:
        remaining_seconds = (job.next_t - datetime.datetime.now(job.next_t.tzinfo)).total_seconds()
        td = datetime.timedelta(seconds=remaining_seconds)
        message += _("▪️ *Texto*: `{data}`\n   *Faltan*: `{rem}`\n   *ID*: `{name}`\n\n").format(data=job.data, rem=str(td).split('.')[0], name=job.name)
    await update.message.reply_text(message, parse_mode='Markdown')

@authorized_only
@rate_limit_and_deduplicate()
async def reminders_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args: await update.message.reply_text(_("Uso: `/delremind <ID>`")); return
    jobs = context.job_queue.get_jobs_by_name(context.args[0])
    if not jobs: await update.message.reply_text(_("❌ No se encontró el recordatorio con ID `{id}`.").format(id=context.args[0])); return
    for job in jobs: job.schedule_removal()
    await update.message.reply_text(_("✅ Recordatorio `{id}` eliminado.").format(id=context.args[0]))

@authorized_only
async def start_weather_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = setup_translation(context)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=_("Por favor, introduce la localidad que quieres consultar, o envía /cancel para anular."), reply_markup=None)
    return AWAITING_LOCATION

@authorized_only
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = setup_translation(context)
    await update.message.reply_text(_("Operación cancelada."), reply_markup=main_menu_keyboard(_))
    return ConversationHandler.END

@super_admin_only
@rate_limit_and_deduplicate()
async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args or not context.args[0].isdigit(): await update.message.reply_text(_("Uso: `/adduser <ID_de_usuario_numérico>`")); return
    new_user_id, users_config = int(context.args[0]), cargar_usuarios()
    if new_user_id not in users_config["authorized_users"]:
        users_config["authorized_users"].append(new_user_id)
        if guardar_usuarios(users_config):
            await update.message.reply_text(_("✅ Usuario `{id}` añadido.").format(id=new_user_id)); logging.info(f"Usuario {new_user_id} añadido por {update.effective_user.id}")
        else: await update.message.reply_text(_("❌ Error al guardar el fichero de usuarios."))
    else: await update.message.reply_text(_("ℹ️ El usuario `{id}` ya estaba autorizado.").format(id=new_user_id))

@super_admin_only
@rate_limit_and_deduplicate()
async def deluser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args or not context.args[0].isdigit(): await update.message.reply_text(_("Uso: `/deluser <ID_de_usuario_numérico>`")); return
    user_to_delete, users_config = int(context.args[0]), cargar_usuarios()
    if user_to_delete == users_config["super_admin_id"]: await update.message.reply_text(_("⛔ No puedes eliminar al super administrador.")); return
    if user_to_delete in users_config["authorized_users"]:
        users_config["authorized_users"].remove(user_to_delete)
        if guardar_usuarios(users_config):
            await update.message.reply_text(_("✅ Usuario `{id}` eliminado.").format(id=user_to_delete)); logging.info(f"Usuario {user_to_delete} eliminado por {update.effective_user.id}")
        else: await update.message.reply_text(_("❌ Error al guardar el fichero de usuarios."))
    else: await update.message.reply_text(_("ℹ️ El usuario `{id}` no se encontraba.").format(id=user_to_delete))

@super_admin_only
@rate_limit_and_deduplicate()
async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    users_config = cargar_usuarios()
    user_ids, super_admin_id = users_config.get("authorized_users", []), users_config.get("super_admin_id")
    if not user_ids: await update.message.reply_text(_("ℹ️ No hay ningún usuario autorizado en la lista.")); return
    message_lines = [_("👥 **Lista de Usuarios Autorizados**\n")]
    for user_id in user_ids:
        message_lines.append(_("👑 *Super Admin*: `{id}`").format(id=user_id) if user_id == super_admin_id else _("👤 *Usuario*: `{id}`").format(id=user_id))
    await update.message.reply_text("\n".join(message_lines), parse_mode='Markdown')


@authorized_only
async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    config = cargar_configuracion()
    is_photo = bool(update.message.photo)

    # Determinar el tipo de fichero y el directorio de destino
    if is_photo:
        dir_key = "image_directory"
        file_to_dl = update.message.photo[-1] # La foto de mayor resolución
        original_name = f"{file_to_dl.file_id}.jpg" # Las fotos no tienen nombre, usamos el ID
    else:
        dir_key = "file_directory"
        file_to_dl = update.message.document
        original_name = file_to_dl.file_name

    target_dir = config.get(dir_key)
    if not target_dir:
        await update.message.reply_text(_("❌ La carpeta de destino `{key}` no está configurada.").format(key=dir_key))
        return

    try:
        # Generar un timestamp para el nombre del fichero
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # --- LA CORRECCIÓN CLAVE ESTÁ AQUÍ ---
        # Usamos 'filename_root' en lugar de '_' para evitar sobrescribir la función de traducción.
        filename_root, extension = os.path.splitext(original_name)
        
        if not extension: # Si no hay extensión, ponemos una por defecto
            extension = ".dat" if not is_photo else ".jpg"

        # Crear el nuevo nombre de fichero seguro
        prefix = "image" if is_photo else "file"
        new_filename = f"{prefix}_{timestamp}{extension}"

        expanded_dir = os.path.expanduser(target_dir)
        dest_path = os.path.join(expanded_dir, new_filename)

        os.makedirs(expanded_dir, exist_ok=True)
        file = await context.bot.get_file(file_to_dl.file_id)
        await file.download_to_drive(dest_path)
        
        logging.info(f"Archivo '{original_name}' guardado como '{new_filename}' por {update.effective_user.id}")

        # Ahora la variable `_` es la función correcta y esta llamada funcionará
        success_message = _("✅ Archivo guardado con éxito.\n\n"
                          "   - **Nombre Original:** `{orig}`\n"
                          "   - **Guardado Como:** `{new}`").format(
                              orig=escape_markdown(original_name), 
                              new=escape_markdown(new_filename)
                          )
        await update.message.reply_text(success_message, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error al subir archivo: {e}")
        # Y esta llamada en el bloque de error también funcionará
        await update.message.reply_text(_("❌ Ocurrió un error: `{err}`").format(err=escape_markdown(str(e))))

@authorized_only
@rate_limit_and_deduplicate()
async def get_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if len(context.args) < 2 or context.args[0] not in ['imagenes', 'ficheros']: await update.message.reply_text(_("Uso: `/get <imagenes|ficheros> <nombre_archivo>`")); return
    folder_key = "image_directory" if context.args[0] == 'imagenes' else "file_directory"
    filename, config = " ".join(context.args[1:]), cargar_configuracion()
    base_dir = os.path.expanduser(config.get(folder_key, ''))
    file_path = os.path.join(base_dir, os.path.basename(filename))
    if os.path.abspath(file_path).startswith(os.path.abspath(base_dir)) and os.path.exists(file_path):
        await update.message.reply_text(_("🚀 Enviando `{name}`...").format(name=escape_markdown(filename)))
        try:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
        except Exception as e:
            await update.message.reply_text(_("❌ Error al enviar el archivo: `{err}`").format(err=escape_markdown(str(e))))
    else:
        await update.message.reply_text(_("❌ El archivo `{name}` no se encuentra.").format(name=escape_markdown(filename)))

async def periodic_monitoring_check(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Ejecutando comprobación de monitorización periódica...")
    config, users_config = cargar_configuracion(), cargar_usuarios()
    thresholds, super_admin_id = config.get("monitoring_thresholds", {}), users_config.get("super_admin_id")
    if not super_admin_id or not thresholds: logging.warning("Monitorización periódica deshabilitada."); return
    try:
        if (cpu := psutil.cpu_percent(interval=1)) > (cpu_t := thresholds.get('cpu_usage_percent', 90)):
            msg = f"⚠️ CPU ALERT: Usage > {cpu_t}% (current: {cpu:.1f}%)."
            await context.bot.send_message(super_admin_id, msg); logging.warning(msg)
    except Exception as e: logging.error(f"Error en chequeo periódico de CPU: {e}")
    try:
        if (disk := psutil.disk_usage('/')).percent > (disk_t := thresholds.get('disk_usage_percent', 95)):
            msg = f"⚠️ DISK ALERT: Usage of (/) > {disk_t}% (current: {disk.percent:.1f}%)."
            await context.bot.send_message(super_admin_id, msg); logging.warning(msg)
    except Exception as e: logging.error(f"Error en chequeo periódico de Disco: {e}")
