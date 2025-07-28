# bot_interactivo.py
# MODIFICADO: Punto de entrada principal. Configura e inicia el bot.
# VERSION: 2.5 
# AUTHOR: Oscar Gimenez Blasco & Gemini para LANG, menus, el README.md y la p..a identacion en python.

import logging
import sys
import html
import traceback

from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram.constants import ParseMode

# Importamos desde los nuevos módulos
from state import SECRETS, CONFIG, USERS_DATA, PERSISTENCE_FILE
from custom_persistence import JsonPersistence
from bot_handlers import (
    start_command, help_command, button_callback_handler,
    ping_command, traceroute_command, nmap_command, dig_command, whois_command,
    resources_command, disk_command, processes_command, systeminfo_command,
    logs_command, docker_command_handler, analyze_command,
    adduser_command, deluser_command, listusers_command,
    handle_file_upload, get_file_command,
    periodic_monitoring_check, periodic_log_check,
    fortune_command,
    ask_command, askpro_command,
    remind_command, reminders_list_command, reminders_delete_command,
    language_command,
    start_weather_conversation, receive_weather_location, cancel_conversation, AWAITING_LOCATION,
    fail2ban_command
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
    """Manejador de errores global. Notifica al super admin."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    message = (f"Ha ocurrido una excepción:\n<pre>{html.escape(tb_string)}</pre>")

    # Trunca el mensaje si es demasiado largo para Telegram
    if len(message) > 4096:
        message = message[:4000] + "\n... (mensaje truncado)</pre>"

    super_admin_id = USERS_DATA.get("super_admin_id")
    if super_admin_id:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="🤖 Vaya, algo ha salido mal. He notificado al administrador.")
        await context.bot.send_message(chat_id=super_admin_id, text=message, parse_mode=ParseMode.HTML)


def main(token: str) -> None:
    """Inicia el bot, registra los manejadores y comienza a escuchar."""
    persistence = JsonPersistence(filepath=PERSISTENCE_FILE)
    application = Application.builder().token(token).persistence(persistence).build()
    application.add_error_handler(error_handler)

    # --- REGISTRO DE MANEJADORES ---
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
    
    # Manejador de botones (debe ir después de las conversacione))
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # --- TAREAS PERIÓDICAS (Job Queue) ---
    job_queue = application.job_queue

    # Tarea de monitorización de umbrales
    threshold_config = CONFIG.get("monitoring_thresholds", {})
    if (interval := threshold_config.get("check_interval_minutes", 0) * 60) > 0:
        job_queue.run_repeating(periodic_monitoring_check, interval=interval, first=10)
        logger.info(f"Tarea de monitorización de umbrales configurada cada {interval/60} minutos.")

    # Tarea de monitorización de logs
    log_config = CONFIG.get("log_monitoring", {})
    if log_config.get("enabled", False) and (interval := log_config.get("check_interval_seconds", 0)) > 0:
        job_queue.run_repeating(periodic_log_check, interval=interval, first=15)
        logger.info(f"Tarea de monitorización de logs configurada cada {interval} segundos.")

    logger.info("El bot se está iniciando...")
    application.run_polling()


if __name__ == "__main__":
    # Ahora el token se obtiene del módulo de estado que ya lo ha validado
    main(token=SECRETS["TELEGRAM_TOKEN"])
