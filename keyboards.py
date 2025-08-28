# keyboards.py
# MODULO NUEVO: Centraliza la creación de todos los teclados Inline.

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from state import CONFIG # Importamos la configuración cargada

def main_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("📊 Monitorización"), callback_data='menu:monitor')],
        [InlineKeyboardButton(_("⚙️ Administración"), callback_data='menu:admin')],
        [InlineKeyboardButton(_("🛠️ Herramientas de Red"), callback_data='menu:network_tools')],
        [InlineKeyboardButton(_("🚀 Herramientas Avanzadas"), callback_data='menu:advanced_tools')],
        [InlineKeyboardButton(_("🔧 Utilidades"), callback_data='menu:utils')],
        [InlineKeyboardButton(_("🐳 Gestión Docker"), callback_data='menu:docker')],
        [InlineKeyboardButton(_("🛡️ Fail2Ban"), callback_data='menu:fail2ban')],
        [InlineKeyboardButton(_("📦 Gestión de Backups"), callback_data='menu:backups')],
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

def network_tools_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("📡 Ping"), callback_data='network:select_ping')],
        [InlineKeyboardButton(_("🗺️ Traceroute"), callback_data='network:select_traceroute')],
        [InlineKeyboardButton(_("🔬 Escaneo Nmap (-A)"), callback_data='network:select_nmap')],
        [InlineKeyboardButton(_("🌐 Dig (DNS Lookup)"), callback_data='network:select_dig')],
        [InlineKeyboardButton(_("👤 Whois"), callback_data='network:select_whois')],
        [InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')]
    ])

def advanced_tools_menu_keyboard(_):
    """Menú para las nuevas herramientas avanzadas."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(_("📄 Analizar Logs"), callback_data='advanced:analizar_logs_info')],
        [InlineKeyboardButton(_("ℹ️ Info de Fichero (muestra)"), callback_data='advanced:muestra_info')],
        [InlineKeyboardButton(_("🔌 Conexiones de Red (muestrared)"), callback_data='advanced:muestrared_info')],
        [InlineKeyboardButton(_("🌐 Herramientas de Red Avanzadas (redes)"), callback_data='advanced:redes_info')],
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

def language_menu_keyboard(_):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Español 🇪🇸", callback_data='set_lang:es')],
        [InlineKeyboardButton("English 🇬🇧", callback_data='set_lang:en')],
        [InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')]
    ])

def docker_menu_keyboard(_):
    containers = CONFIG.get("docker_containers_allowed", [])
    keyboard = [[InlineKeyboardButton(_("Listar Contenedores (`docker ps`)"), callback_data='docker:ps')]]
    if containers:
        keyboard.append([InlineKeyboardButton(_("Ver Logs de Contenedor"), callback_data='docker:select_logs')])
        keyboard.append([InlineKeyboardButton(_("Reiniciar Contenedor"), callback_data='docker:select_restart')])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')])
    return InlineKeyboardMarkup(keyboard)

def fail2ban_menu_keyboard(_):
    jails = CONFIG.get("fail2ban_jails", [])
    keyboard = [[InlineKeyboardButton(_("Estado General"), callback_data='fail2ban:status')]]
    if jails:
        keyboard.append([InlineKeyboardButton(_("Ver Estado de Jaula"), callback_data='fail2ban:select_jail')])
        keyboard.append([InlineKeyboardButton(_("Desbloquear IP"), callback_data='fail2ban:unban_ip_start')])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver"), callback_data='menu:main')])
    return InlineKeyboardMarkup(keyboard)

# --- Teclados Dinámicos ---

def dynamic_keyboard_from_config(config_key: str, action_prefix: str, back_button_cb: str, back_button_text: str, _):
    """Función genérica para crear teclados a partir de una lista en la config."""
    items = CONFIG.get(config_key, {})
    keyboard = []
    
    # Maneja tanto diccionarios como listas
    item_keys = items.keys() if isinstance(items, dict) else items
    
    if not item_keys:
        keyboard.append([InlineKeyboardButton(_("No hay elementos definidos"), callback_data='no_op')])
    else:
        for name in item_keys:
            keyboard.append([InlineKeyboardButton(f"▶️ {name}", callback_data=f"{action_prefix}:{name}")])

    keyboard.append([InlineKeyboardButton(f"⬅️ {back_button_text}", callback_data=back_button_cb)])
    return InlineKeyboardMarkup(keyboard)

def dynamic_backup_script_keyboard(_):
    return dynamic_keyboard_from_config("backup_scripts", "backup:run", "menu:backups", _("Volver a Backups"), _)

def dynamic_script_keyboard(script_type: str, _):
    """
    Crea un teclado dinámico para scripts, filtrando por tipo (sh o py).
    """
    all_scripts = CONFIG.get("scripts", {})
    keyboard = []
    
    # Determina la extensión del fichero a buscar (.sh o .py)
    # El script_type que llega es 'shell' o 'python', lo convertimos a extensión
    extension = ".sh" if script_type == 'shell' else ".py"
    
    # Filtra los scripts por la extensión
    filtered_scripts = {
        name: info for name, info in all_scripts.items() 
        if info.get("path", "").endswith(extension)
    }

    if not filtered_scripts:
        keyboard.append([InlineKeyboardButton(_("No hay scripts de tipo '{ext}' definidos").format(ext=extension), callback_data='no_op')])
    else:
        # Crea un botón para cada script filtrado
        for name, info in filtered_scripts.items():
            # Usa la descripción del script si está disponible, si no, el nombre
            description = info.get("description", name)
            keyboard.append([InlineKeyboardButton(f"▶️ {description}", callback_data=f"run:{script_type}:{name}")])

    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Admin"), callback_data='menu:admin')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_services_action_keyboard(action: str, _):
    action_icon_map = {'status': '🔎', 'start': '▶️', 'stop': '⏹️', 'restart': '🔄'}
    icon = action_icon_map.get(action, '⚙️')
    services = CONFIG.get("servicios_permitidos", [])
    keyboard = []
    for service in services:
        keyboard.append([InlineKeyboardButton(f"{icon} {service}", callback_data=f"service:{action}:{service}")])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Monitor"), callback_data='menu:monitor')])
    return InlineKeyboardMarkup(keyboard)
    
def dynamic_logs_keyboard(_):
    return dynamic_keyboard_from_config("allowed_logs", "log:view", "menu:monitor", _("Volver a Monitor"), _)

def dynamic_host_keyboard(action: str, _):
    hosts = CONFIG.get("servidores", [])
    keyboard = []
    for server in hosts:
        if server.get("host"):
            keyboard.append([InlineKeyboardButton(f'🎯 {server.get("nombre")}', callback_data=f"run:{action}:{server.get('host')}")])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Herramientas"), callback_data='menu:network_tools')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_docker_container_keyboard(action: str, _):
    containers = CONFIG.get("docker_containers_allowed", [])
    keyboard = []
    for container in containers:
        keyboard.append([InlineKeyboardButton(f"{action.capitalize()} '{container}'", callback_data=f"docker:{action}:{container}")])
    keyboard.append([InlineKeyboardButton(_("⬅️ Volver a Docker"), callback_data='menu:docker')])
    return InlineKeyboardMarkup(keyboard)

def dynamic_fail2ban_jail_keyboard(_):
    return dynamic_keyboard_from_config("fail2ban_jails", "fail2ban:status", "menu:fail2ban", _("Volver a Fail2Ban"), _)
