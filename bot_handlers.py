# bot_handlers.py
# MODIFICADO: Manejadores de comandos y callbacks. Lógica de la aplicación.

import logging
import os
import re
import ipaddress
import sys
import time
import datetime
import asyncio
import psutil
from functools import wraps

from telegram.ext import ContextTypes, ConversationHandler
from telegram import Update
from telegram.helpers import escape_markdown

# Módulos refactorizados
from state import CONFIG, USERS_DATA, guardar_usuarios
from localization import setup_translation, get_system_translator
from keyboards import * # Importamos todos los teclados
import core_functions as core
import system_utils as system

# --- Lock para tareas pesadas ---
HEAVY_TASK_LOCK = asyncio.Lock()
AWAITING_LOCATION = 1 # Estado para conversación

# --- Decoradores ---

def authorized_only(func):
    """Decorador para permitir el acceso solo a usuarios autorizados."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        _ = setup_translation(context)
        user_id = update.effective_user.id
        
        # Usamos los datos cargados desde el módulo state
        authorized_list = USERS_DATA.get("authorized_users", [])
        
        if user_id not in authorized_list:
            logging.warning(f"ACCESO DENEGADO para el usuario ID: {user_id}.")
            if update.callback_query:
                await update.callback_query.answer(_("❌ No tienes permiso."), show_alert=True)
            else:
                await update.message.reply_text(_("❌ No tienes permiso para usar este bot."))
            return

        return await func(update, context, *args, **kwargs)
    return wrapped

def super_admin_only(func):
    """Decorador para permitir el acceso solo al super administrador."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        _ = setup_translation(context)
        user_id = update.effective_user.id
        
        if user_id != USERS_DATA.get("super_admin_id"):
            logging.warning(f"Intento de ejecución de comando de super admin por usuario no autorizado: {user_id}")
            if update.callback_query:
                 await update.callback_query.answer(_("⛔ Comando solo para super admin."), show_alert=True)
            else:
                 await update.message.reply_text(_("⛔ Este comando solo puede ser usado por el super administrador."))
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def rate_limit_and_deduplicate(limit_seconds: int = 5):
    """Decorador para prevenir el flood y duplicados."""
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            if not update.message: return await func(update, context, *args, **kwargs)

            user_id = update.effective_user.id
            current_time, message_text = time.time(), update.message.text
            last_message = context.user_data.get('last_message', {})
            
            if message_text and message_text == last_message.get('text') and (current_time - last_message.get('time', 0)) < limit_seconds:
                logging.warning(f"Mensaje duplicado bloqueado para el usuario {user_id}: '{message_text}'")
                return

            context.user_data['last_message'] = {'text': message_text, 'time': current_time}
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator

# --- Funciones de Validación de Entradas ---

def is_safe_grep_pattern(pattern: str) -> bool:
    if not pattern or len(pattern) > 100: return False
    # Prohíbe metacaracteres complejos que pueden causar ReDoS.
    if re.search(r'[\\*+?(){}|\[\]\^$]', pattern):
         logging.warning(f"Patrón de búsqueda bloqueado: {pattern}")
         return False
    return True

def is_valid_target(target: str) -> bool:
    if not target or len(target) > 255: return False
    try:
        ipaddress.ip_address(target)
        return True
    except ValueError:
        pass
    if target.startswith('-') or target.endswith('-'): return False
    # Expresión regular estricta para hostnames (RFC 1123)
    hostname_pattern = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$")
    return bool(hostname_pattern.fullmatch(target))

# --- Comandos Principales (/comando) ---

@authorized_only
@rate_limit_and_deduplicate()
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await update.message.reply_text(
        _("¡Hola {first_name}! 👋\n\nSelecciona una opción del menú para empezar.").format(first_name=update.effective_user.first_name),
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
    fortune_text = await asyncio.to_thread(system.get_fortune_text_cmd, _)
    await thinking_message.edit_text(fortune_text, parse_mode='Markdown')


# --- Manejador de Botones ---
@authorized_only
async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    query = update.callback_query
    await query.answer()
    data = query.data

    # --- 1. Manejo de cambio de idioma (acción simple) ---
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

    # --- 2. Manejo de menús y acciones sin parámetros ---
    menu_map = {
        'menu:main': (_("Menú Principal"), main_menu_keyboard),
        'menu:monitor': (_("Menú de Monitorización"), monitor_menu_keyboard),
        'menu:admin': (_("Menú de Administración"), admin_menu_keyboard),
        'menu:backups': (_("📦 Gestión de Backups"), backups_menu_keyboard),
        'backups:list': (_("Selecciona el backup a ejecutar:"), dynamic_backup_script_keyboard),
        'menu:utils': (_("🔧 Menú de Utilidades"), utilities_menu_keyboard),
        'menu:language': (_("Selecciona tu idioma:"), language_menu_keyboard),
        'menu:network_tools': (_("🛠️ Herramientas de Red"), network_tools_menu_keyboard),
        'menu:docker': (_("🐳 Gestión Docker"), docker_menu_keyboard),
        'menu:fail2ban': (_("🛡️ Gestión de Fail2Ban"), fail2ban_menu_keyboard),
        'menu:logs': (_("Selecciona un log:"), dynamic_logs_keyboard),
        'menu:services_status': (_("Selecciona un servicio para ver su estado:"), lambda _=_: dynamic_services_action_keyboard('status', _)),
        'menu:services_start': (_("Selecciona un servicio para INICIAR:"), lambda _=_: dynamic_services_action_keyboard('start', _)),
        'menu:services_stop': (_("Selecciona un servicio para PARAR:"), lambda _=_: dynamic_services_action_keyboard('stop', _)),
        'menu:services_restart': (_("Selecciona un servicio para REINICIAR:"), lambda _=_: dynamic_services_action_keyboard('restart', _)),
        'menu:run_script_shell': (_("Selecciona script de Shell a ejecutar:"), lambda _=_: dynamic_script_keyboard('shell', _)),
        'menu:run_script_python': (_("Selecciona script de Python a ejecutar:"), lambda _=_: dynamic_script_keyboard('python', _)),
        'network:select_ping': (_("📡 **Ping**: Elige un objetivo"), lambda _=_: dynamic_host_keyboard('ping', _)),
        'network:select_traceroute': (_("🗺️ **Traceroute**: Elige un objetivo"), lambda _=_: dynamic_host_keyboard('traceroute', _)),
        'network:select_nmap': (_("🔬 **Nmap**: Elige un objetivo"), lambda _=_: dynamic_host_keyboard('nmap', _)),
        'network:select_dig': (_("🌐 **Dig**: Elige un objetivo"), lambda _=_: dynamic_host_keyboard('dig', _)),
        'network:select_whois': (_("👤 **Whois**: Elige un objetivo"), lambda _=_: dynamic_host_keyboard('whois', _)),
        'docker:select_logs': (_("Selecciona contenedor para ver logs:"), lambda _=_: dynamic_docker_container_keyboard('logs', _)),
        'docker:select_restart': (_("Selecciona contenedor para reiniciar:"), lambda _=_: dynamic_docker_container_keyboard('restart', _)),
        'fail2ban:select_jail': (_("Selecciona una jaula para ver su estado:"), lambda _=_: dynamic_fail2ban_jail_keyboard(_))
    }

    if data in menu_map:
        text, keyboard_func = menu_map[data]
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=keyboard_func(_))
        return

    if data == 'menu:help':
        await query.message.reply_text(get_help_text(_), parse_mode='Markdown')
        return

    if data == 'menu:fortune':
        await query.edit_message_text("🍀...", parse_mode='Markdown')
        fortune_text = await asyncio.to_thread(system.get_fortune_text_cmd, _)
        await query.edit_message_text(fortune_text, parse_mode='Markdown', reply_markup=main_menu_keyboard(_))
        return

    if data == 'refresh_main':
        time_str = datetime.datetime.now().strftime('%H:%M:%S')
        await query.edit_message_text(_("Menú actualizado a las {time}").format(time=time_str), reply_markup=main_menu_keyboard(_))
        return

    # --- 3. Manejo de acciones con parámetros (formato: tipo:nombre:parametro) ---
    parts = data.split(':', 2)
    action_type = parts[0]
    action_name = parts[1] if len(parts) > 1 else None
    param = parts[2] if len(parts) > 2 else None

    # Lógica de Monitorización
    if action_type == 'monitor':
        monitor_map = {
            'status_all': core.get_status_report_text, 'resources': core.get_resources_text,
            'disk': system.get_disk_usage_text, 'processes': system.get_processes_text, 'systeminfo': core.get_system_info_text,
        }
        if action_name in monitor_map:
            await query.edit_message_text(_("Obteniendo {action_name}...").format(action_name=action_name.replace('_', ' ')))
            reporte = await asyncio.to_thread(monitor_map[action_name], _)
            await query.edit_message_text(reporte, parse_mode='Markdown', reply_markup=monitor_menu_keyboard(_))

    # Lógica de Ejecución (Herramientas de Red y Scripts)
    elif action_type == 'run':
        # Sub-lógica para herramientas de red
        tool_map = {'ping': system.do_ping, 'traceroute': system.do_traceroute, 'nmap': system.do_nmap, 'dig': system.do_dig, 'whois': system.do_whois}
        if action_name in tool_map:
            if not is_valid_target(param):
                await query.edit_message_text(_("❌ El objetivo '{param}' no es válido.").format(param=param))
                return

            heavy_tasks = ['nmap', 'traceroute']
            is_heavy = action_name in heavy_tasks
            if is_heavy and HEAVY_TASK_LOCK.locked():
                await query.answer(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."), show_alert=True)
                return

            thinking_msg = _("⏳ Ejecutando `{action}` en `{param}`... (Puede tardar)").format(action=action_name, param=param) if is_heavy else _("⏳ Ejecutando `{action}` en `{param}`...").format(action=action_name, param=param)
            await query.edit_message_text(thinking_msg, parse_mode='Markdown')

            if is_heavy:
                async with HEAVY_TASK_LOCK:
                    result = await asyncio.to_thread(tool_map[action_name], param, _)
            else:
                result = await asyncio.to_thread(tool_map[action_name], param, _)

            await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_host_keyboard(action_name, _))

        # su p.. madre.!
        # Sub-lógica para scripts, AHORA DENTRO de "elif action_type == 'run'"
        elif action_name in ['shell', 'python']:
            script_type = action_name
            script_name = param
            if HEAVY_TASK_LOCK.locked():
                await query.answer(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."), show_alert=True)
                return
            async with HEAVY_TASK_LOCK:
                await query.edit_message_text(
                    _("⏳ Ejecutando script '{name}'...").format(name=script_name)
                )
                resultado = await asyncio.to_thread(system.run_script, script_type, script_name, _)

            await query.edit_message_text(
                resultado,
                reply_markup=dynamic_script_keyboard(script_type, _)
            )

    # Lógica para Administración
    elif action_type == 'admin' and action_name == 'check_cron':
        await query.edit_message_text(_("🗓️ Obteniendo tareas de Cron..."))
        salida = await asyncio.to_thread(core.get_cron_tasks, _)
        await query.edit_message_text(salida, parse_mode='Markdown', reply_markup=admin_menu_keyboard(_))

    # Lógica para Fail2Ban
    elif action_type == 'fail2ban':
        if action_name == 'status':
            await query.edit_message_text(_("🛡️ Obteniendo estado..."))
            result = await asyncio.to_thread(core.fail2ban_status, _, param) # param es la jaula (o None)
            await query.edit_message_text(result, parse_mode='Markdown', reply_markup=fail2ban_menu_keyboard(_))

    # Lógica para Logs
    elif action_type == 'log' and action_name == 'view':
        await query.edit_message_text(_("📜 Obteniendo últimas 20 líneas de `{param}`...").format(param=param), parse_mode='Markdown')
        result = await asyncio.to_thread(core.get_log_content, param, 20, _)
        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_logs_keyboard(_))

    # Lógica para Servicios
    elif action_type == 'service':
        if param == 'telegram_bot' and action_name in ['stop', 'restart']:
            await query.edit_message_text(_("🛡️ **Acción denegada por seguridad.**\nNo puedes parar o reiniciar el propio bot desde aquí."), parse_mode='Markdown')
            return

        if action_name == 'status':
            await query.edit_message_text(_("🔎 Verificando estado de `{param}`...").format(param=param))
            result = await asyncio.to_thread(core.get_service_status, param, _)
        else:
            await query.edit_message_text(_("⏳ Ejecutando `{action}` en `{param}`...").format(action=action_name, param=param))
            result = await asyncio.to_thread(core.manage_service, param, action_name, _)

        await query.edit_message_text(result, parse_mode='Markdown', reply_markup=dynamic_services_action_keyboard(action_name, _))

    # Lógica para Backups
    elif action_type == 'backup' and action_name == 'run':
        if HEAVY_TASK_LOCK.locked():
            await query.answer(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."), show_alert=True)
            return
        async with HEAVY_TASK_LOCK:
            await query.edit_message_text(_("⏳ Ejecutando backup '{script}'... (Puede tardar)").format(script=param), parse_mode='Markdown')
            resultado = await asyncio.to_thread(system.run_script, "shell", param, _) # Asumimos que los backups son .sh
        await query.edit_message_text(resultado, parse_mode='Markdown', reply_markup=dynamic_backup_script_keyboard(_))
####
@super_admin_only
@rate_limit_and_deduplicate()
async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(_("Uso: `/adduser <ID_de_usuario_numérico>`"))
        return
    
    new_user_id = int(context.args[0])
    
    # Accedemos a los datos desde el módulo state
    if new_user_id not in USERS_DATA["authorized_users"]:
        USERS_DATA["authorized_users"].append(new_user_id)
        if guardar_usuarios(): # La función de guardado ya no necesita argumentos
            await update.message.reply_text(_("✅ Usuario `{id}` añadido.").format(id=new_user_id))
            logging.info(f"Usuario {new_user_id} añadido por {update.effective_user.id}")
        else: 
            await update.message.reply_text(_("❌ Error al guardar el fichero de usuarios."))
    else: 
        await update.message.reply_text(_("ℹ️ El usuario `{id}` ya estaba autorizado.").format(id=new_user_id))

@super_admin_only
@rate_limit_and_deduplicate()
async def deluser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(_("Uso: `/deluser <ID_de_usuario_numérico>`"))
        return
    
    user_to_delete = int(context.args[0])

    if user_to_delete == USERS_DATA["super_admin_id"]:
        await update.message.reply_text(_("⛔ No puedes eliminar al super administrador."))
        return
        
    if user_to_delete in USERS_DATA["authorized_users"]:
        USERS_DATA["authorized_users"].remove(user_to_delete)
        if guardar_usuarios():
            await update.message.reply_text(_("✅ Usuario `{id}` eliminado.").format(id=user_to_delete))
            logging.info(f"Usuario {user_to_delete} eliminado por {update.effective_user.id}")
        else:
            await update.message.reply_text(_("❌ Error al guardar el fichero de usuarios."))
    else:
        await update.message.reply_text(_("ℹ️ El usuario `{id}` no se encontraba.").format(id=user_to_delete))

@super_admin_only
@rate_limit_and_deduplicate()
async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    user_ids = USERS_DATA.get("authorized_users", [])
    super_admin_id = USERS_DATA.get("super_admin_id")

    if not user_ids:
        await update.message.reply_text(_("ℹ️ No hay ningún usuario autorizado en la lista."))
        return
        
    message_lines = [_("👥 **Lista de Usuarios Autorizados**\n")]
    for user_id in user_ids:
        role = "👑 Super Admin" if user_id == super_admin_id else "👤 Usuario"
        message_lines.append(_("{role}: `{id}`").format(role=_(role), id=user_id))
        
    await update.message.reply_text("\n".join(message_lines), parse_mode='Markdown')

@authorized_only
async def handle_file_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    is_photo = bool(update.message.photo)

    # Determinar el tipo de fichero y el directorio de destino
    if is_photo:
        dir_key = "image_directory"
        file_to_dl = update.message.photo[-1] # La foto de mayor resolución
        original_name = f"{file_to_dl.file_id}.jpg"
    else:
        dir_key = "file_directory"
        file_to_dl = update.message.document
        original_name = file_to_dl.file_name

    target_dir = CONFIG.get(dir_key)
    if not target_dir:
        await update.message.reply_text(_("❌ La carpeta de destino `{key}` no está configurada.").format(key=dir_key))
        return

    try:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_root, extension = os.path.splitext(original_name)
        
        if not extension:
            extension = ".dat" if not is_photo else ".jpg"

        prefix = "image" if is_photo else "file"
        new_filename = f"{prefix}_{timestamp}{extension}"

        expanded_dir = os.path.expanduser(target_dir)
        dest_path = os.path.join(expanded_dir, new_filename)

        os.makedirs(expanded_dir, exist_ok=True)
        file = await context.bot.get_file(file_to_dl.file_id)
        await file.download_to_drive(dest_path)
        
        logging.info(f"Archivo '{original_name}' guardado como '{new_filename}' por {update.effective_user.id}")

        success_message = _("✅ Archivo guardado con éxito.\n\n"
                          "   - **Nombre Original:** `{orig}`\n"
                          "   - **Guardado Como:** `{new}`").format(
                              orig=escape_markdown(original_name), 
                              new=escape_markdown(new_filename)
                          )
        await update.message.reply_text(success_message, parse_mode='Markdown')

    except Exception as e:
        logging.error(f"Error al subir archivo: {e}")
        await update.message.reply_text(_("❌ Ocurrió un error: `{err}`").format(err=escape_markdown(str(e))))

@authorized_only
@rate_limit_and_deduplicate()
async def get_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if len(context.args) < 2 or context.args[0] not in ['imagenes', 'ficheros']:
        await update.message.reply_text(_("Uso: `/get <imagenes|ficheros> <nombre_archivo>`"))
        return

    folder_key = "image_directory" if context.args[0] == 'imagenes' else "file_directory"
    filename = " ".join(context.args[1:])
    base_dir = os.path.expanduser(CONFIG.get(folder_key, ''))
    
    # Medida de seguridad para evitar Path Traversal
    file_path = os.path.join(base_dir, os.path.basename(filename))
    if not os.path.abspath(file_path).startswith(os.path.abspath(base_dir)):
        await update.message.reply_text(_("❌ Acceso denegado."))
        return

    if os.path.exists(file_path):
        await update.message.reply_text(_("🚀 Enviando `{name}`...").format(name=escape_markdown(filename)))
        try:
            with open(file_path, 'rb') as f:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=f)
        except Exception as e:
            await update.message.reply_text(_("❌ Error al enviar el archivo: `{err}`").format(err=escape_markdown(str(e))))
    else:
        await update.message.reply_text(_("❌ El archivo `{name}` no se encuentra.").format(name=escape_markdown(filename)))

@authorized_only
@rate_limit_and_deduplicate()
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    model_name = CONFIG.get("gemini_api", {}).get("flash_model")
    if not model_name:
        await update.message.reply_text(_("❌ El modelo 'flash' no está configurado."))
        return
    if not context.args:
        await update.message.reply_text(_("Uso: /ask <tu pregunta>\n(Modelo: {model})").format(model=model_name))
        return

    question = " ".join(context.args)
    thinking_message = await update.message.reply_text(_("🤔 Pensando con Gemini Flash..."))
    result = await asyncio.to_thread(core.ask_gemini_model, question, model_name, _)
    await thinking_message.edit_text(result, parse_mode='Markdown')

@super_admin_only
@rate_limit_and_deduplicate()
async def askpro_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    model_name = CONFIG.get("gemini_api", {}).get("pro_model")
    if not model_name:
        await update.message.reply_text(_("❌ El modelo 'pro' no está configurado."))
        return
    if not context.args:
        await update.message.reply_text(_("Uso: /askpro <pregunta compleja>\n(Modelo: {model})").format(model=model_name))
        return

    question = " ".join(context.args)
    thinking_message = await update.message.reply_text(_("🧠 Pensando con Gemini Pro... (puede tardar)"))
    result = await asyncio.to_thread(core.ask_gemini_model, question, model_name, _)
    await thinking_message.edit_text(result, parse_mode='Markdown')
# --- Resto de Comandos y Lógica ---

async def _handle_async_command(update: Update, context: ContextTypes.DEFAULT_TYPE, func, thinking_msg: str, _):
    message_to_edit = await update.message.reply_text(thinking_msg)
    result = await asyncio.to_thread(func, _)
    await message_to_edit.edit_text(result, parse_mode='Markdown')

async def _handle_async_network_command(update: Update, context: ContextTypes.DEFAULT_TYPE, func, usage: str, thinking_prefix: str, _):
    if not context.args:
        await update.message.reply_text(_("Uso: {use}").format(use=usage))
        return
    target = context.args[0]
    if not is_valid_target(target):
        await update.message.reply_text(_("❌ El objetivo '{target}' no es válido.").format(target=target))
        return

    message_to_edit = await update.message.reply_text(f"{thinking_prefix} `{target}`...")
    result = await asyncio.to_thread(func, target, _)
    await message_to_edit.edit_text(result, parse_mode='Markdown')

@authorized_only
@rate_limit_and_deduplicate()
async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    model_name = CONFIG.get("gemini_api", {}).get("flash_model")
    if not model_name:
        await update.message.reply_text(_("❌ El modelo 'flash' no está configurado."))
        return

    if len(context.args) < 2:
        await update.message.reply_text(_("Uso: /analyze <recurso> <pregunta...>\nRecursos: `status`, `resources`, `processes`, `disk`"))
        return

    resource = context.args[0].lower()
    question = " ".join(context.args[1:])
    thinking_message = await update.message.reply_text(_("📊 Obteniendo datos para el análisis..."))

    source_data_map = {
        "status": core.get_status_report_text,
        "resources": core.get_resources_text,
        "processes": system.get_processes_text,
        "disk": system.get_disk_usage_text
    }
    if resource not in source_data_map:
        await thinking_message.edit_text(_("❌ Recurso no válido. Usa: `status`, `resources`, `processes`, `disk`"))
        return

    # Obtenemos los datos del sistema en un hilo separado
    source_data = await asyncio.to_thread(source_data_map[resource], _)

    await thinking_message.edit_text(_("🧠 Analizando datos con Gemini flash..."))

    final_prompt = f"Eres un experto SRE con 20 años de experiencia. Analiza los siguientes datos de un servidor Linux y responde a la pregunta del usuario de forma clara y concisa, ofreciendo recomendaciones.\n\n--- DATOS ---\n{source_data}\n\n--- PREGUNTA ---\n{question}"

    # Llamamos al modelo de IA en un hilo separado
    result = await asyncio.to_thread(core.ask_gemini_model, final_prompt, model_name, _)

    await thinking_message.edit_text(result, parse_mode='Markdown')


async def reminder_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
    _ = setup_translation(context)
    job = context.job
    await context.bot.send_message(chat_id=job.chat_id, text=_("🔔 **Recordatorio:**\n\n{data}").format(data=job.data))

@authorized_only
@rate_limit_and_deduplicate()
async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    match = re.match(r'^\s*/remind\s+"([^"]+)"\s+(?:en|in)\s+(.+)$', update.message.text, re.IGNORECASE)
    if not match:
        await update.message.reply_text(_('Formato: `/remind "Texto" en 1d 2h 30m`'), parse_mode='Markdown')
        return

    reminder_text = match.group(1)
    time_str = match.group(2)
    delay_seconds = core.parse_time_to_seconds(time_str)

    if delay_seconds <= 0:
        await update.message.reply_text(_("Duración inválida."))
        return

    job_name = f"reminder_{update.effective_chat.id}_{int(time.time())}"
    context.job_queue.run_once(
        reminder_callback,
        delay_seconds,
        data=reminder_text,
        chat_id=update.effective_chat.id,
        name=job_name
    )
    await update.message.reply_text(
        _("✅ Recordatorio programado para *{txt}* en *{t}*.\nID: `{id}`").format(
            txt=reminder_text, t=time_str, id=job_name
        ),
        parse_mode='Markdown'
    )

@authorized_only
@rate_limit_and_deduplicate()
async def reminders_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    prefix = f"reminder_{update.effective_chat.id}_"
    active_jobs = [j for j in context.job_queue.jobs() if j.name and j.name.startswith(prefix)]

    if not active_jobs:
        await update.message.reply_text(_("ℹ️ No hay recordatorios programados."))
        return

    message = [_("🗓️ **Recordatorios Pendientes:**\n")]
    for job in active_jobs:
        if job.next_t:
            remaining_seconds = (job.next_t - datetime.datetime.now(job.next_t.tzinfo)).total_seconds()
            td = datetime.timedelta(seconds=max(0, remaining_seconds))
            remaining_str = str(td).split('.')[0]
            message.append(
                _("▪️ *Texto*: `{data}`\n   *Faltan*: `{rem}`\n   *ID*: `{name}`\n").format(
                    data=job.data, rem=remaining_str, name=job.name
                )
            )
    await update.message.reply_text("\n".join(message), parse_mode='Markdown')

@authorized_only
@rate_limit_and_deduplicate()
async def reminders_delete_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args:
        await update.message.reply_text(_("Uso: `/delremind <ID>`"))
        return
        
    job_name_to_delete = context.args[0]
    jobs = context.job_queue.get_jobs_by_name(job_name_to_delete)
    
    if not jobs:
        await update.message.reply_text(_("❌ No se encontró el recordatorio con ID `{id}`.").format(id=job_name_to_delete))
        return
        
    for job in jobs:
        job.schedule_removal()
        
    await update.message.reply_text(_("✅ Recordatorio `{id}` eliminado.").format(id=job_name_to_delete))

@super_admin_only
@rate_limit_and_deduplicate()
async def fail2ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args:
        await update.message.reply_text(_("Uso: `/fail2ban <status|unban> [IP]`"))
        return
    
    subcommand = context.args[0].lower()
    
    if subcommand == 'unban':
        if len(context.args) < 2:
            await update.message.reply_text(_("Uso: `/fail2ban unban <IP>`"))
            return
        ip_address = context.args[1]
        # Validación de IP
        if not is_valid_target(ip_address):
            await update.message.reply_text(_("❌ Formato de IP no válido."))
            return

    thinking_message = await update.message.reply_text(_("🛡️ Procesando comando Fail2Ban..."))

    if subcommand == 'status':
        result = await asyncio.to_thread(core.fail2ban_status, _)
        await thinking_message.edit_text(result, parse_mode='Markdown')
    elif subcommand == 'unban':
        ip_address = context.args[1]
        result = await asyncio.to_thread(core.fail2ban_unban, ip_address, _)
        await thinking_message.edit_text(result, parse_mode='Markdown')
    else:
        await thinking_message.edit_text(_("Comando no reconocido. Usa `status` o `unban`."))

@authorized_only
async def start_weather_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = setup_translation(context)
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=_("Por favor, introduce la localidad que quieres consultar, o envía /cancel para anular."), reply_markup=None)
    # Devuelve el estado que indica que estamos esperando una ubicación
    return AWAITING_LOCATION

@authorized_only
@rate_limit_and_deduplicate(limit_seconds=10) # Mayor tiempo para evitar envíos múltiples
async def receive_weather_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = setup_translation(context)
    location = update.message.text
    thinking_message = await update.message.reply_text(f"🌦️ {_('Consultando el tiempo para')} `{location}`...")
    
    # Llama a la función de system_utils
    weather_report = await asyncio.to_thread(system.get_weather_text_cmd, location, _)

    await thinking_message.edit_text(
            weather_report, 
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard(_)
    )
    # Finaliza la conversación
    return ConversationHandler.END

@authorized_only
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _ = setup_translation(context)
    await update.message.reply_text(_("Operación cancelada."), reply_markup=main_menu_keyboard(_))
    # Finaliza la conversación
    return ConversationHandler.END

@authorized_only
@rate_limit_and_deduplicate()
async def docker_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args:
        await update.message.reply_text(_("Uso: `/docker <ps|logs|restart> [contenedor] [líneas]`"))
        return

    thinking_message = await update.message.reply_text("🐳 Procesando comando docker...")
    
    action = context.args[0]
    container = context.args[1] if len(context.args) > 1 else None
    lines = int(context.args[2]) if len(context.args) > 2 and context.args[2].isdigit() else 20
    
    result = await asyncio.to_thread(core.docker_logic, action, _, container, lines)
    await thinking_message.edit_text(result, parse_mode='Markdown')

@authorized_only
@rate_limit_and_deduplicate()
async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_network_command(update, context, system.do_ping, "/ping <host>", _("📡 Haciendo ping a"), _)

@authorized_only
@rate_limit_and_deduplicate()
async def traceroute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if HEAVY_TASK_LOCK.locked():
        await update.message.reply_text(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."))
        return
    async with HEAVY_TASK_LOCK:
        await _handle_async_network_command(update, context, system.do_traceroute, "/traceroute <host>", _("🗺️ Ejecutando traceroute a"), _)

@authorized_only
@rate_limit_and_deduplicate()
async def nmap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if HEAVY_TASK_LOCK.locked():
        await update.message.reply_text(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."))
        return
    async with HEAVY_TASK_LOCK:
        await _handle_async_network_command(update, context, system.do_nmap, "/nmap <host>", _("🔬 Ejecuturando Nmap a"), _)

@authorized_only
@rate_limit_and_deduplicate()
async def dig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_network_command(update, context, system.do_dig, "/dig <dominio>", _("🌐 Realizando consulta DIG para"), _)

@authorized_only
@rate_limit_and_deduplicate()
async def whois_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_network_command(update, context, system.do_whois, "/whois <dominio>", _("👤 Realizando consulta WHOIS para"), _)

@authorized_only
@rate_limit_and_deduplicate()
async def resources_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_command(update, context, core.get_resources_text, _("💻 Obteniendo recursos..."), _)

@authorized_only
@rate_limit_and_deduplicate()
async def disk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_command(update, context, system.get_disk_usage_text, _("💾 Obteniendo uso de disco..."), _)

@authorized_only
@rate_limit_and_deduplicate()
async def processes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_command(update, context, system.get_processes_text, _("⚙️ Listando procesos..."), _)

@authorized_only
@rate_limit_and_deduplicate()
async def systeminfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    await _handle_async_command(update, context, core.get_system_info_text, _("ℹ️ Obteniendo información del sistema..."), _)

@authorized_only
@rate_limit_and_deduplicate()
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args:
        await update.message.reply_text(_("Uso: `/logs <alias> [líneas]` o `/logs search <alias> <patrón>`"))
        return

    if context.args[0] == 'search':
        if len(context.args) < 3:
            await update.message.reply_text(_("Uso: `/logs search <alias> <patrón>`"), parse_mode='Markdown'); return
        
        alias_log = context.args[1]
        search_pattern = " ".join(context.args[2:])

        if not is_safe_grep_pattern(search_pattern):
            await update.message.reply_text(_("❌ El patrón de búsqueda contiene caracteres no permitidos o potencialmente peligrosos."))
            return

        if HEAVY_TASK_LOCK.locked():
            await update.message.reply_text(_("⏳ Hay otra tarea pesada en ejecución. Por favor, espera."))
            return
        async with HEAVY_TASK_LOCK:
            thinking_message = await update.message.reply_text("📜 Buscando en logs... (Puede tardar)")
            result = await asyncio.to_thread(core.search_log, alias_log, search_pattern, _) 
    else:
        alias_log = context.args[0]
        num_lines = int(context.args[1]) if len(context.args) > 1 and context.args[1].isdigit() else 20
        thinking_message = await update.message.reply_text(f"📜 Obteniendo últimas {num_lines} líneas de `{alias_log}`...")
        result = await asyncio.to_thread(core.get_log_content, alias_log, num_lines, _)

    await thinking_message.edit_text(result, parse_mode='Markdown')

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
          "--- **Gestión  de archvos y Admin** ---\n"
          "**/docker** `<ps|logs|restart> [contenedor]`: Gestiona Docker.\n\n"
          "**/get** `<imagenes|ficheros> <fichero>`: Descarga un archivo del servidor.\n"
          "*Para subir un fichero o imagen, simplemente envíalo al chat.*\n\n"
          "--- **Herramientas de Red** ---\n"
          "**/ping**, **/traceroute**, **/nmap**, **/dig**, **/whois** `<objetivo>`\n\n"
          "--- **Recordatorios** ---\n"
          "**/remind** `\"texto\" in <tiempo>`: Programa un recordatorio.\n\n"
          "**/reminders**: Lista tus recordatorios pendientes.\n"
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

# ... (resto de las funciones...)

@super_admin_only
@rate_limit_and_deduplicate()
async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ = setup_translation(context)
    if not context.args or not context.args[0].isdigit(): 
        await update.message.reply_text(_("Uso: `/adduser <ID_de_usuario_numérico>`")); return
    
    new_user_id = int(context.args[0])
    
    if new_user_id not in USERS_DATA["authorized_users"]:
        USERS_DATA["authorized_users"].append(new_user_id)
        if guardar_usuarios():
            await update.message.reply_text(_("✅ Usuario `{id}` añadido.").format(id=new_user_id))
            logging.info(f"Usuario {new_user_id} añadido por {update.effective_user.id}")
        else: 
            await update.message.reply_text(_("❌ Error al guardar el fichero de usuarios."))
    else: 
        await update.message.reply_text(_("ℹ️ El usuario `{id}` ya estaba autorizado.").format(id=new_user_id))

# --- Tareas Periódicas ---
async def periodic_log_check(context: ContextTypes.DEFAULT_TYPE):
    _ = get_system_translator()
    logging.info("Ejecutando comprobación de monitorización de logs...")
    alerts = await asyncio.to_thread(core.check_watched_logs, _)
    if alerts and USERS_DATA.get("super_admin_id"):
        for alert in alerts:
            try:
                await context.bot.send_message(chat_id=USERS_DATA["super_admin_id"], text=alert, parse_mode='Markdown')
                await asyncio.sleep(1)
            except Exception as e:
                logging.error(f"No se pudo enviar la alerta de log al super_admin: {e}")

async def periodic_monitoring_check(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Ejecutando comprobación de monitorización periódica de recursos...")
    thresholds = CONFIG.get("monitoring_thresholds", {})
    super_admin_id = USERS_DATA.get("super_admin_id")
    if not super_admin_id or not thresholds: return

    try:
        if (cpu := psutil.cpu_percent(interval=1)) > (cpu_t := thresholds.get('cpu_usage_percent', 90)):
            msg = f"⚠️ ALERTA CPU: Uso > {cpu_t}% (actual: {cpu:.1f}%)"
            await context.bot.send_message(super_admin_id, msg)
            logging.warning(msg)
    except Exception as e:
        logging.error(f"Error en chequeo periódico de CPU: {e}")
        
    try:
        if (disk := psutil.disk_usage('/')).percent > (disk_t := thresholds.get('disk_usage_percent', 95)):
            msg = f"⚠️ ALERTA DISCO: Uso de (/) > {disk_t}% (actual: {disk.percent:.1f}%)"
            await context.bot.send_message(super_admin_id, msg)
            logging.warning(msg)
    except Exception as e:
        logging.error(f"Error en chequeo periódico de Disco: {e}")
