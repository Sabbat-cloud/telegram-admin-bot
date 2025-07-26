# BOT INTERACTIVO PARA TELEGRAM
# VERSION: 2.1
# AUTHOR: Oscar Gimenez Blasco & Gemini para menus y soporte LANG (quien dijo que la IA no ayuda??)

import logging
import sys
import json
import html
import traceback
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

from telegram.constants import ParseMode
from custom_persistence import JsonPersistence
from core_functions import cargar_configuracion, cargar_usuarios
from bot_handlers import (
    start_command, help_command, button_callback_handler,
    ping_command, traceroute_command, nmap_command, dig_command, whois_command,
    resources_command, disk_command, processes_command, systeminfo_command,
    logs_command, docker_command_handler, analyze_command,
    adduser_command, deluser_command, listusers_command,
    handle_file_upload, get_file_command,
    periodic_monitoring_check,
    fortune_command,
    ask_command, askpro_command,
    remind_command, reminders_list_command, reminders_delete_command,
    language_command,
    start_weather_conversation, receive_weather_location, cancel_conversation, AWAITING_LOCATION,
    fail2ban_command, periodic_log_check
)

# --- CONFIGURACIÓN DE LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    message = (f"Ha ocurrido una excepción:\n<pre>{html.escape(tb_string)}</pre>")
    max_length = 4096
    if len(message) > max_length:
        message = message[:max_length - 100] + "\n... (mensaje truncado)</pre>"

    users_config = cargar_usuarios()
    super_admin_id = users_config.get("super_admin_id")
    if super_admin_id:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="🤖 Vaya, algo ha salido mal. He notificado al administrador.")
        await context.bot.send_message(chat_id=super_admin_id, text=message, parse_mode=ParseMode.HTML)


def main(token: str) -> None:
    """Inicia el bot, registra los manejadores y comienza a escuchar."""
    config = cargar_configuracion()

    persistence = JsonPersistence(filepath="bot_persistence.json")
    #persistence = PicklePersistence(filepath="bot_persistence.pickle")
    application = Application.builder().token(token).persistence(persistence).build()
    application.add_error_handler(error_handler)

    # Comandos principales
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("fortune", fortune_command))
    application.add_handler(CommandHandler("language", language_command))

    # Recordatorios
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_list_command))
    application.add_handler(CommandHandler("delremind", reminders_delete_command))

    # Comandos de IA
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("askpro", askpro_command))
    application.add_handler(CommandHandler("analyze", analyze_command))

    # Comandos de monitorización
    application.add_handler(CommandHandler("resources", resources_command))
    application.add_handler(CommandHandler("disk", disk_command))
    application.add_handler(CommandHandler("processes", processes_command))
    application.add_handler(CommandHandler("systeminfo", systeminfo_command))
    application.add_handler(CommandHandler("logs", logs_command))

    # Herramientas de red
    application.add_handler(CommandHandler("ping", ping_command))
    application.add_handler(CommandHandler("traceroute", traceroute_command))
    application.add_handler(CommandHandler("nmap", nmap_command))
    application.add_handler(CommandHandler("dig", dig_command))
    application.add_handler(CommandHandler("whois", whois_command))

    # Docker
    application.add_handler(CommandHandler("docker", docker_command_handler))

    # Fail2Ban (Super Admin)
    application.add_handler(CommandHandler("fail2ban", fail2ban_command))

    # Gestión de usuarios (Super Admin)
    application.add_handler(CommandHandler("adduser", adduser_command))
    application.add_handler(CommandHandler("deluser", deluser_command))
    application.add_handler(CommandHandler("listusers", listusers_command))

    # Gestión de archivos
    application.add_handler(CommandHandler("get", get_file_command))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file_upload))

    # Conversation Handler para el tiempo
    weather_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_weather_conversation, pattern='^weather:start$')],
        states={AWAITING_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_weather_location)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)]
    )
    application.add_handler(weather_conv_handler)

    # Manejador de botones (debe ir después de las conversaciones)
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # --- TAREAS PERIÓDICAS (Job Queue) ---
    job_queue = application.job_queue

    # Tarea 1: Monitorización de umbrales (CPU/Disco)
    check_interval = config.get("monitoring_thresholds", {}).get("check_interval_minutes", 5) * 60
    if check_interval > 0:
        job_queue.run_repeating(periodic_monitoring_check, interval=check_interval, first=10)
        logger.info(f"Tarea de monitorización de umbrales configurada cada {check_interval/60} minutos.")

    # Tarea 2: Monitorización activa de logs
    log_check_config = config.get("log_monitoring", {})
    if log_check_config.get("enabled", False):
        log_interval = log_check_config.get("check_interval_seconds", 60)
        job_queue.run_repeating(periodic_log_check, interval=log_interval, first=15)
        logger.info(f"Tarea de monitorización de logs configurada cada {log_interval} segundos.")

    logger.info("El bot se está iniciando...")
    application.run_polling()

if __name__ == "__main__":
    # Importamos la nueva función aquí
    from core_functions import cargar_secretos

    secretos = cargar_secretos()

    # Comprobamos si el diccionario de secretos se ha cargado
    # y si contiene la clave que necesitamos.
    if not secretos or "TELEGRAM_TOKEN" not in secretos:
        # El mensaje de error crítico ya se habrá mostrado desde la función
        sys.exit(1)

    # Pasamos el token leído del fichero a la función main
    main(token=secretos["TELEGRAM_TOKEN"])
