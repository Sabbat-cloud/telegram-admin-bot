# bot_handlers.py
# Todos los manejadores.
import logging
import os
import re
import subprocess
import sys
import time
from functools import wraps
import datetime 

from telegram.ext import ContextTypes, ConversationHandler

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.helpers import escape_markdown

from core_functions import *
from localization import setup_translation

# --- Definición de estados para la conversación ---
AWAITING_LOCATION = 1

def authorized_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        _ = setup_translation(context)
        user_id = update.effective_user.id
        config = cargar_configuracion()
        if user_id not in config.get("telegram", {}).get("authorized_users", []):
            logging.warning(f"Acceso no autorizado denegado para el usuario con ID: {user_id}")
            if update.callback_query:
                await update.callback_query.answer(_("❌ No tienes permiso."), show_alert=True)
            else:
                await update.message.reply_text(_("❌ No tienes permiso para usar este bot."))
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def super_admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        _ = setup_translation(context)
        user_id = update.effective_user.id
        config = cargar_configuracion()
        if user_id != config.get("telegram", {}).get("super_admin_id"):
            logging.warning(f"Intento de ejecución de comando de super admin por usuario no autorizado: {user_id}")
            await update.message.reply_text(_("⛔ Este comando solo puede ser usado por el super administrador."))
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def main_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("📊 Monitorización"), callback_data='menu:monitor')],
        [InlineKeyboardButton(_("⚙️ Administración"), callback_data='menu:admin')],
        [InlineKeyboardButton(_("🛠️ Herramientas de Red"), callback_data='menu:network_tools')],
        [InlineKeyboardButton(_("🔧 Utilidades"), callback_data='menu:utils')],
        [InlineKeyboardButton(_("🐳 Gestión Docker"), callback_data='menu:docker')],
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
        [InlineKeyboardButton(_("Procesos (`ps aux`)"), callback_data='monitor:processes')],
        [InlineKeyboardButton(_("Info. Sistema (`uname -a`)"), callback_data='monitor:systeminfo')],
        [InlineKeyboardButton(_("Ver Logs"), callback_data='menu:logs')],
        [InlineKeyboardButton(_("Estado de un Servicio"), callback_data='menu:services')],
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

def dynamic_services_keyboard(_):
    services = cargar_configuracion().get("servicios_permitidos", [])
    keyboard = []
    for service in services:
        keyboard.append([InlineKeyboardButton(_("Estado de '{service}'").format(service=service), callback_data=f"service:status:{service}")])
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


@authorized_only
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    user = update.effective_user
    await update.message.reply_text(
        _("¡Hola {first_name}! 👋\n\nSelecciona una opción del menú para empezar.").format(first_name=user.first_name),
        reply_markup=main_menu_keyboard(_)
    )

@authorized_only
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await update.message.reply_text(get_help_text(_), parse_mode='Markdown')

@authorized_only
async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await update.message.reply_text(
        _("Selecciona tu idioma:"),
        reply_markup=language_menu_keyboard(_)
    )

# --- MANEJADOR DE BOTONES (CALLBACKS) ---
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
        'menu:utils': (_("🔧 Menú de Utilidades"), utilities_menu_keyboard),
        'menu:language': (_("Selecciona tu idioma:"), language_menu_keyboard),
        'menu:files': (_("Menú de Gestión de Archivos\n\nPara subir, simplemente envía el archivo."), files_menu_keyboard),
        'menu:network_tools': (_("🛠️ Herramientas de Red"), network_tools_menu_keyboard),
        'menu:docker': (_("🐳 Gestión Docker"), docker_menu_keyboard),
        'menu:logs': (_("Selecciona un log:"), dynamic_logs_keyboard),
        'menu:services': (_("Selecciona un servicio para ver su estado:"), dynamic_services_keyboard),
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
        await query.answer()
        await query.message.reply_text(get_help_text(_), parse_mode='Markdown')
        return
    elif data == 'menu:fortune':
        await query.answer()
        fortune_text = get_fortune_text(_)
        await query.message.reply_text(fortune_text, parse_mode='Markdown')
        return
    if data == 'refresh_main':
        time_str = datetime.datetime.now().strftime('%H:%M:%S') # <--- CORREGIDO
        await query.edit_message_text(_("Menú actualizado a las {time}").format(time=time_str), reply_markup=main_menu_keyboard(_))
        return

    parts = data.split(':', 2)
    action_type, action_name = parts[0], parts[1]

    param = parts[2] if len(parts) > 2 else None

    if action_type == 'monitor':
        await query.edit_message_text(_("Obteniendo {action_name}...").format(action_name=action_name.replace('_', ' ')))
        report_map = {
            'status_all': get_status_report_text, 'resources': get_resources_text,
            'disk': get_disk_usage_text, 'processes': get_processes_text, 'systeminfo': get_system_info_text,
        }
        if action_name in report_map:
            reporte = report_map[action_name](_)
            await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard(_))

    elif action_type == 'run':
        if action_name in ['ping', 'traceroute', 'nmap', 'dig', 'whois']:
            await query.edit_message_text(_("Ejecutando `{action_name}` en `{param}`...").format(action_name=action_name, param=param), parse_mode='Markdown')
            tool_map = {'ping': do_ping, 'traceroute': do_traceroute, 'nmap': do_nmap, 'dig': do_dig, 'whois': do_whois}
            result = tool_map[action_name](param, _)
            await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_host_keyboard(action_name, _))

        elif action_name == 'shell':
            config = cargar_configuracion()
            script_path_raw = config["scripts_permitidos"].get(param)
            script_path = os.path.expanduser(script_path_raw)
            await query.edit_message_text(_("🚀 Ejecutando script de Shell '{param}'...").format(param=param), parse_mode='Markdown')
            try:
                proc = subprocess.run([script_path], capture_output=True, text=True, timeout=120, check=True)
                salida = _("✅ **Script '{param}' ejecutado:**\n\n```\n{output}\n```").format(param=param, output=proc.stdout or '(Sin salida)')
                await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=dynamic_script_keyboard('shell', _))
            except Exception as e:
                await query.edit_message_text(_("❌ Error al ejecutar {param}: {error}").format(param=param, error=e), reply_markup=dynamic_script_keyboard('shell', _))

        elif action_name == 'python':
            config = cargar_configuracion()
            script_path_raw = config["python_scripts_permitidos"].get(param)
            script_path = os.path.expanduser(script_path_raw)
            await query.edit_message_text(_("🐍 Ejecutando script de Python '{param}'...").format(param=param), parse_mode='Markdown')
            try:
                proc = subprocess.run([sys.executable, script_path], capture_output=True, text=True, timeout=300, check=True)
                salida = _("✅ **Script '{param}' ejecutado:**\n\n```\n{output}\n```").format(param=param, output=proc.stdout or '(Sin salida)')
                await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=dynamic_script_keyboard('python', _))
            except Exception as e:
                await query.edit_message_text(_("❌ Error al ejecutar {param}: {error}").format(param=param, error=e), reply_markup=dynamic_script_keyboard('python', _))

    elif action_type == 'docker':
        if action_name == 'ps':
            await query.edit_message_text(_("🐳 Listando contenedores..."), parse_mode='Markdown')
            result = docker_command('ps', _)
            await query.edit_message_text(result, parse_mode='Markdown', reply_markup=docker_menu_keyboard(_))
        elif action_name in ['logs', 'restart']:
            await query.edit_message_text(_("Ejecutando `{action_name}` en `{param}`...").format(action_name=action_name, param=param), parse_mode='Markdown')
            lines = 20 if action_name == 'logs' else None
            result = docker_command(action_name, _, param, num_lines=lines)
            await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_docker_container_keyboard(action_name, _))

    elif action_type == 'log' and action_name == 'view':
        await query.edit_message_text(_("📜 Obteniendo últimas 20 líneas de `{param}`...").format(param=param), parse_mode='Markdown')
        result = get_log_lines(param, 20, _)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_logs_keyboard(_))

    elif action_type == 'service' and action_name == 'status':
        await query.edit_message_text(_("🔎 Verificando estado de `{param}`...").format(param=param), parse_mode='Markdown')
        try:
            proc = subprocess.run(['systemctl', 'status', param], capture_output=True, text=True, timeout=10)
            output = proc.stdout + proc.stderr
            status_icon, status_text = (_("✅"), _("Activo")) if "active (running)" in output else \
                                       (_("❌"), _("Inactivo")) if "inactive (dead)" in output else \
                                       (_("🔥"), _("Ha fallado")) if "failed" in output else \
                                       (_("❔"), _("Desconocido"))
            log_lines = re.findall(r'●.*|Loaded:.*|Active:.*|Main PID:.*|(?<=─ ).*', output)
            detalle = "\n".join(log_lines[-5:])
            reporte = _("{status_icon} **Estado de `{param}`: {status_text}**\n\n```\n{details}\n```").format(status_icon=status_icon, param=param, status_text=status_text, details=detalle or _('No hay detalles.'))
            await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=dynamic_services_keyboard(_))
        except Exception as e:
             await query.edit_message_text(_("❌ Error al verificar {param}: {error}").format(param=param, error=e), reply_markup=dynamic_services_keyboard(_))

    elif action_type == 'files' and action_name.startswith('list_'):
        folder_type = action_name.split('_')[1]
        folder_key = "image_directory" if folder_type == 'imagenes' else "file_directory"
        config = cargar_configuracion()
        target_dir = os.path.expanduser(config.get(folder_key, ''))
        if not target_dir or not os.path.isdir(target_dir):
            await query.edit_message_text(_("❌ La carpeta para `{folder_type}` no está configurada o no existe.").format(folder_type=folder_type), reply_markup=files_menu_keyboard(_))
            return
        files = os.listdir(target_dir)
        files_list = "\n".join(f"`{escape_markdown(f)}`" for f in files)
        message = _("ℹ️ La carpeta `{folder_type}` está vacía.").format(folder_type=folder_type) if not files else \
                  _("📁 **Archivos en `{folder_type}`:**\n{files_list}\n\nPara descargar, usa `/get {folder_type} nombre_del_archivo`").format(folder_type=folder_type, files_list=files_list)
        if len(message) > 4096: message = message[:4090] + "\n..."
        await query.edit_message_text(message, parse_mode='Markdown', reply_markup=files_menu_keyboard(_))

    elif action_type == 'admin':
        if action_name == 'check_cron':
            await query.edit_message_text(_("🗓️ Obteniendo tareas de Cron..."), parse_mode='Markdown')
            try:
                proc = subprocess.run('crontab -l', shell=True, capture_output=True, text=True, timeout=10)
                if proc.stderr and "no crontab for" in proc.stderr:
                    salida = _("ℹ️ No hay tareas de cron configuradas para el usuario actual.")
                elif proc.returncode != 0:
                    salida = _("❌ **Error al leer crontab:**\n`{error}`").format(error=proc.stderr)
                else:
                    salida = _("🗓️ **Tareas de Cron (`crontab -l`):**\n\n```\n{output}\n```").format(output=proc.stdout or '(Vacío)')
            except Exception as e:
                salida = _("❌ **Error inesperado** al consultar cron: {error}").format(error=e)
            await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=admin_menu_keyboard(_))


@authorized_only
async def fortune_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    fortune_text = get_fortune_text(_)
    await update.message.reply_text(fortune_text, parse_mode='Markdown')

@authorized_only
async def _handle_network_command(update: Update, context: ContextTypes.DEFAULT_TYPE, tool_func, usage: str, message_prefix: str, _):
    if not context.args:
        await update.message.reply_text(_("Uso: {usage}").format(usage=usage))
        return
    target = context.args[0]
    await update.message.reply_text(f"{message_prefix} `{target}`...", parse_mode='Markdown')
    result = tool_func(target, _)
    await update.message.reply_text(result, parse_mode='Markdown')

@authorized_only
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_network_command(update, context, do_ping, "/ping <host>", _("📡 Haciendo ping a"), _)

@authorized_only
async def traceroute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_network_command(update, context, do_traceroute, "/traceroute <host>", _("🗺️ Ejecutando traceroute a"), _)

@authorized_only
async def nmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_network_command(update, context, do_nmap, "/nmap <host>", _("🔬 Ejecutando Nmap a"), _)

@authorized_only
async def dig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_network_command(update, context, do_dig, "/dig <dominio>", _("🌐 Realizando consulta DIG para"), _)

@authorized_only
async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_network_command(update, context, do_whois, "/whois <dominio>", _("👤 Realizando consulta WHOIS para"), _)

@authorized_only
async def resources_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await update.message.reply_text(get_resources_text(_), parse_mode='Markdown')

@authorized_only
async def disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await update.message.reply_text(get_disk_usage_text(_), parse_mode='Markdown')

@authorized_only
async def processes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await update.message.reply_text(get_processes_text(_), parse_mode='Markdown')

@authorized_only
async def systeminfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await update.message.reply_text(get_system_info_text(_), parse_mode='Markdown')

@authorized_only
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args:
        config = cargar_configuracion()
        available_logs = ", ".join(config.get("allowed_logs", {}).keys())
        await update.message.reply_text(_("Uso: `/logs <alias> [líneas]` o `/logs search <alias> <patrón>`\nDisponibles: `{available_logs}`").format(available_logs=available_logs), parse_mode='Markdown')
        return
    if context.args[0] == 'search':
        if len(context.args) < 3:
            await update.message.reply_text(_("Uso: `/logs search <alias> <patrón>`"), parse_mode='Markdown')
            return
        result = search_log(context.args[1], " ".join(context.args[2:]), _)
    else:
        num_lines = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 20
        result = get_log_lines(context.args[0], num_lines, _)
    await update.message.reply_text(result, parse_mode='Markdown')

@authorized_only
async def docker_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args:
        await update.message.reply_text(_("Uso: `/docker <ps|logs|restart> [contenedor] [líneas]`"))
        return
    action = context.args[0]
    container = context.args[1] if len(context.args) > 1 else None
    lines = int(context.args[2]) if len(context.args) > 2 and context.args[2].isdigit() else 20
    result = docker_command(action, _, container, lines)
    await update.message.reply_text(result, parse_mode='Markdown')

@authorized_only
async def start_weather_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia la conversación para pedir el tiempo y pregunta por la localidad."""
    _ = setup_translation(context)
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text=_("Por favor, introduce la localidad que quieres consultar, o envía /cancel para anular."),
        reply_markup=None # Quitamos los botones para que el usuario solo pueda escribir
    )

    # Le decimos al ConversationHandler que estamos esperando la respuesta del usuario
    return AWAITING_LOCATION

@authorized_only
async def receive_weather_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el mensaje con la localidad, obtiene el tiempo y termina la conversación."""
    _ = setup_translation(context)
    location = update.message.text

    await update.message.reply_text(f"🌦️ {_('Consultando el tiempo para')} `{location}`...")

    weather_report = get_weather_text(location, _)

    await update.message.reply_text(weather_report, parse_mode='Markdown')

    # Terminamos la conversación
    return ConversationHandler.END

@authorized_only
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la conversación actual."""
    _ = setup_translation(context)
    await update.message.reply_text(
        _("Operación cancelada."), 
        reply_markup=main_menu_keyboard(_) # Mostramos de nuevo el menú principal
    )
    return ConversationHandler.END

@super_admin_only
async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(_("Uso: `/adduser <ID_de_usuario_numérico>`"))
        return
    new_user_id = int(context.args[0])
    config = cargar_configuracion()
    if new_user_id not in config["telegram"]["authorized_users"]:
        config["telegram"]["authorized_users"].append(new_user_id)
        if guardar_configuracion(config):
            await update.message.reply_text(_("✅ Usuario `{user_id}` añadido.").format(user_id=new_user_id))
            logging.info(f"Usuario {new_user_id} añadido por {update.effective_user.id}")
        else:
            await update.message.reply_text(_("❌ Error al guardar la configuración."))
    else:
        await update.message.reply_text(_("ℹ️ El usuario `{user_id}` ya estaba autorizado.").format(user_id=new_user_id))

@super_admin_only
async def deluser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(_("Uso: `/deluser <ID_de_usuario_numérico>`"))
        return
    user_to_delete = int(context.args[0])
    config = cargar_configuracion()
    if user_to_delete == config["telegram"]["super_admin_id"]:
        await update.message.reply_text(_("⛔ No puedes eliminar al super administrador."))
        return
    if user_to_delete in config["telegram"]["authorized_users"]:
        config["telegram"]["authorized_users"].remove(user_to_delete)
        if guardar_configuracion(config):
            await update.message.reply_text(_("✅ Usuario `{user_id}` eliminado.").format(user_id=user_to_delete))
            logging.info(f"Usuario {user_to_delete} eliminado por {update.effective_user.id}")
        else:
            await update.message.reply_text(_("❌ Error al guardar la configuración."))
    else:
        await update.message.reply_text(_("ℹ️ El usuario `{user_id}` no se encontraba.").format(user_id=user_to_delete))


@super_admin_only
async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    config = cargar_configuracion()
    user_ids = config.get("telegram", {}).get("authorized_users", [])
    super_admin_id = config.get("telegram", {}).get("super_admin_id")

    if not user_ids:
        await update.message.reply_text(_("ℹ️ No hay ningún usuario autorizado en la lista."))
        return

    message_lines = [_("👥 **Lista de Usuarios Autorizados**\n")]

    for user_id in user_ids:
        if user_id == super_admin_id:
            message_lines.append(_("👑 *Super Admin*: `{user_id}`").format(user_id=user_id))
        else:
            message_lines.append(_("👤 *Usuario*: `{user_id}`").format(user_id=user_id))

    response = "\n".join(message_lines)
    await update.message.reply_text(response, parse_mode='Markdown')

@authorized_only
async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    config = cargar_configuracion()
    is_photo = bool(update.message.photo)
    dir_key = "image_directory" if is_photo else "file_directory"
    file_to_dl = update.message.photo[-1] if is_photo else update.message.document
    original_name = f"{file_to_dl.file_id}.jpg" if is_photo else file_to_dl.file_name
    target_dir = config.get(dir_key)
    if not target_dir:
        await update.message.reply_text(_("❌ La carpeta de destino `{dir_key}` no está configurada.").format(dir_key=dir_key))
        return
    expanded_dir = os.path.expanduser(target_dir)
    dest_path = os.path.join(expanded_dir, os.path.basename(original_name))
    try:
        os.makedirs(expanded_dir, exist_ok=True)
        file = await context.bot.get_file(file_to_dl.file_id)
        await file.download_to_drive(dest_path)
        logging.info(f"Archivo '{dest_path}' subido por {update.effective_user.id}")
        await update.message.reply_text(_("✅ Archivo `{filename}` guardado.").format(filename=escape_markdown(os.path.basename(dest_path))))
    except Exception as e:
        logging.error(f"Error al subir archivo: {e}")
        await update.message.reply_text(_("❌ Ocurrió un error: `{error}`").format(error=escape_markdown(str(e))))

@authorized_only
async def get_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if len(context.args) < 2 or context.args[0] not in ['imagenes', 'ficheros']:
        await update.message.reply_text(_("Uso: `/get <imagenes|ficheros> <nombre_archivo>`"))
        return
    folder_key = "image_directory" if context.args[0] == 'imagenes' else "file_directory"
    filename = " ".join(context.args[1:])
    config = cargar_configuracion()
    base_dir = os.path.expanduser(config.get(folder_key, ''))
    file_path = os.path.join(base_dir, os.path.basename(filename))
    if os.path.abspath(file_path).startswith(os.path.abspath(base_dir)) and os.path.exists(file_path):
        await update.message.reply_text(_("🚀 Enviando `{filename}`...").format(filename=escape_markdown(filename)))
        try:
            await context.bot.send_document(chat_id=update.effective_chat.id, document=open(file_path, 'rb'))
        except Exception as e:
            await update.message.reply_text(_("❌ Error al enviar el archivo: `{error}`").format(error=escape_markdown(str(e))))
    else:
        await update.message.reply_text(_("❌ El archivo `{filename}` no se encuentra.").format(filename=escape_markdown(filename)))

async def periodic_monitoring_check(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Ejecutando comprobación de monitorización periódica...")
    config = cargar_configuracion()
    thresholds = config.get("monitoring_thresholds", {})
    super_admin_id = config.get("telegram", {}).get("super_admin_id")
    if not super_admin_id or not thresholds:
        logging.warning("No se puede ejecutar la monitorización periódica: falta super_admin_id o thresholds.")
        return
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > thresholds.get('cpu_usage_percent', 90):
            msg = f"⚠️ CPU ALERT: Usage has exceeded {thresholds['cpu_usage_percent']}% (current: {cpu_percent:.1f}%)."
            await context.bot.send_message(super_admin_id, msg)
            logging.warning(msg)
    except Exception as e:
        logging.error(f"Error en chequeo periódico de CPU: {e}")
    try:
        disk = psutil.disk_usage('/')
        if disk.percent > thresholds.get('disk_usage_percent', 95):
            msg = f"⚠️ DISK ALERT: Usage of (/) has exceeded {thresholds['disk_usage_percent']}% (current: {disk.percent:.1f}%)."
            await context.bot.send_message(super_admin_id, msg)
            logging.warning(msg)
    except Exception as e:
        logging.error(f"Error en chequeo periódico de Disco: {e}")

@authorized_only
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    config = cargar_configuracion()
    model_name = config.get("gemini_api", {}).get("flash_model")

    if not model_name:
        await update.message.reply_text(_("❌ El modelo 'flash' no está configurado."))
        return

    if not context.args:
        await update.message.reply_text(_("Uso: /ask <tu pregunta>\n(Este comando usa el modelo {model_name})").format(model_name=model_name))
        return

    prompt = " ".join(context.args)
    thinking_message = await update.message.reply_text(_("🤔 Pensando con Gemini Flash..."))

    result = ask_gemini_model(prompt, model_name, _)
    await thinking_message.edit_text(result, parse_mode='Markdown')


@super_admin_only
async def askpro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    config = cargar_configuracion()
    model_name = config.get("gemini_api", {}).get("pro_model")

    if not model_name:
        await update.message.reply_text(_("❌ El modelo 'pro' no está configurado."))
        return

    if not context.args:
        await update.message.reply_text(_("Uso: /askpro <tu pregunta compleja>\n(Este comando usa el modelo de pago {model_name})").format(model_name=model_name))
        return

    prompt = " ".join(context.args)
    thinking_message = await update.message.reply_text(_("🧠 Pensando con Gemini Pro... (puede tardar un poco)"))

    result = ask_gemini_model(prompt, model_name, _)
    await thinking_message.edit_text(result, parse_mode='Markdown')

def get_help_text(_):
    """Retorna el texto de ayuda principal del bot."""
    return (
        _("ℹ️ **Ayuda del Bot**\n\n") +
        _("**/start**: Muestra el menú principal.\n") +
        _("**/help**: Muestra esta ayuda.\n") +
        _("**/fortune**: Muestra una galleta de la fortuna.\n") +
        _("**/ask**: Realiza una consulta a la IA (Gemini Flash).\n") +
        _("**/listusers**: Lista los usuarios con acceso.\n\n") +
        _("**🔔 Recordatorios:**\n") +
        _("**/remind \"texto\" en <tiempo>**: Crea un recordatorio (ej: `1d 2h`).\n") +
        _("**/reminders**: Lista los recordatorios activos.\n") +
        _("**/delremind <ID>**: Borra un recordatorio.\n\n") +
        _("**Monitorización:**\n") +
        _("**/resources**: Reporte de CPU, RAM y Disco.\n") +
        _("**/disk**: Uso de disco detallado (`df -h`).\n") +
        _("**/processes**: Lista de procesos (`ps aux`).\n") +
        _("**/systeminfo**: Información del sistema.\n") +
        _("**/logs** <alias> [líneas]: Muestra las últimas líneas de un log.\n\n") +
        _("**Gestión:**\n") +
        _("**/docker** <ps|logs|restart> [contenedor]: Gestiona Docker.\n") +
        _("*/get* <imagenes|ficheros> <nombre_archivo>: Descarga un archivo.\n\n") +
        _("**Herramientas de Red:**\n") +
        _("*/ping, /traceroute, /nmap, /dig, /whois* <objetivo>\n\n") +
        _("*Solo Super Admin:*\n") +
        _("*/askpro*: Consulta a la IA (Gemini Pro).\n") +
        _("*/adduser* <user\\_id>: Autoriza a un usuario.\n") +
        _("*/deluser* <user\\_id>: Revoca el acceso a un usuario.")
    )

async def reminder_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = setup_translation(context)
    job = context.job
    await context.bot.send_message(chat_id=job.chat_id, text=_("🔔 **Recordatorio:**\n\n{data}").format(data=job.data))

@authorized_only
async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    match = re.match(r'^\s*/remind\s+"([^"]+)"\s+(?:en|in)\s+(.+)$', update.message.text, re.IGNORECASE)

    if not match:
        await update.message.reply_text(
            _('Uso incorrecto. Formato:\n`/remind "Texto del recordatorio" en 1d 2h 30m`'),
            parse_mode='Markdown'
        )
        return

    reminder_text = match.group(1)
    time_str = match.group(2)
    delay_seconds = parse_time_to_seconds(time_str)

    if delay_seconds <= 0:
        await update.message.reply_text(_("Duración inválida. Usa un formato como `1d`, `2h`, `30m` o `10s`."))
        return

    job_name = f"reminder_{update.effective_chat.id}_{int(time.time())}"

    context.job_queue.run_once(
        reminder_callback,
        when=delay_seconds,
        data=reminder_text,
        chat_id=update.effective_chat.id,
        name=job_name
    )

    await update.message.reply_text(
        _("✅ Recordatorio programado.\nTe avisaré sobre: *\"{text}\"*\nDentro de: *{time_str}*.\n\nPuedes borrarlo con:\n`/delremind {job_name}`").format(text=reminder_text, time_str=time_str, job_name=job_name),
        parse_mode='Markdown'
    )

@authorized_only
async def reminders_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    
    active_jobs = [j for j in context.job_queue.jobs() if j.name and j.name.startswith(f"reminder_{update.effective_chat.id}_")]

    if not active_jobs:
        await update.message.reply_text(_("ℹ️ No hay recordatorios programados."))
        return

    message = _("🗓️ **Recordatorios Pendientes:**\n\n")
    for job in active_jobs:
        # La propiedad `next_t` es un objeto datetime.datetime ya timezone-aware
        remaining_seconds = (job.next_t - datetime.datetime.now(job.next_t.tzinfo)).total_seconds() # <--- CORRECTO
        td = datetime.timedelta(seconds=remaining_seconds) # <--- CORREGIDO
        message += (
            _("▪️ *Texto*: `{data}`\n   *Faltan*: `{remaining}`\n   *ID*: `{name}`\n\n").format(
                data=job.data, remaining=str(td).split('.')[0], name=job.name
            )
        )

    await update.message.reply_text(message, parse_mode='Markdown')

@authorized_only
async def reminders_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args:
        await update.message.reply_text(_("Uso: `/delremind <ID_del_recordatorio>`"))
        return

    job_name = context.args[0]
    jobs = context.job_queue.get_jobs_by_name(job_name)

    if not jobs:
        await update.message.reply_text(_("❌ No se encontró ningún recordatorio con el ID `{job_name}`.").format(job_name=job_name))
        return

    for job in jobs:
        job.schedule_removal()

    await update.message.reply_text(_("✅ Recordatorio `{job_name}` eliminado correctamente.").format(job_name=job_name))
