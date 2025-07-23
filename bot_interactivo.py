# BOT INTERACTIVO PARA TELEGRAM
# VERSION: 2.0
# AUTHOR: Oscar Gimenez Blasco & Gemini, menus y locales.
#

import logging
import sys
import json
import html
import traceback
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, PicklePersistence, ConversationHandler
from telegram.constants import ParseMode

# Importa los manejadores y funciones de configuración
from core_functions import cargar_configuracion
from bot_handlers import (
    start_command, help_command, button_callback_handler,
    ping_command, traceroute_command, nmap_command, dig_command, whois_command,
    resources_command, disk_command, processes_command, systeminfo_command,
    logs_command, docker_command_handler,
    adduser_command, deluser_command, listusers_command,
    handle_file_upload, get_file_command,
    periodic_monitoring_check,
    fortune_command,
    ask_command,
    askpro_command,
    remind_command, reminders_list_command, reminders_delete_command,
    language_command,
    start_weather_conversation, receive_weather_location, cancel_conversation, AWAITING_LOCATION
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


# Manejador de errores.
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Loguea el error y envía un mensaje al super admin con el traceback."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    message = (
        f"Ha ocurrido una excepción al procesar una actualización:\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )
    max_length = 4096
    if len(message) > max_length:
        message = message[:max_length - 100] + "\n... (mensaje truncado)</pre>"

    config = cargar_configuracion()
    super_admin_id = config.get("telegram", {}).get("super_admin_id")
    if super_admin_id:
        if isinstance(update, Update) and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🤖 Vaya, algo ha salido mal. He notificado al administrador."
            )
        await context.bot.send_message(
            chat_id=super_admin_id,
            text=message,
            parse_mode=ParseMode.HTML
        )



def main() -> None:
    """Inicia el bot, registra los manejadores y comienza a escuchar."""
    config = cargar_configuracion()
    token = config.get("telegram", {}).get("token")
    if not token:
        logger.critical("No se encontró el token de Telegram en configbot.json. Saliendo.")
        sys.exit(1)


    # --- HABILITAR PERSISTENCIA ---
    # Crea un archivo llamado 'bot_persistence.pickle' para guardar los datos.
    persistence = PicklePersistence(filepath="bot_persistence.pickle")

    #Añadimos .persistence(persistence) al contructor de la aplicacion.
    application = Application.builder().token(token).persistence(persistence).build()
    # --- REGISTRO DE MANEJADORES ---
    application.add_error_handler(error_handler)

    # Comandos principales
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("fortune", fortune_command))
    application.add_handler(CommandHandler("language", language_command))

    # --- RECORDATORIOS ---
    application.add_handler(CommandHandler("remind", remind_command))
    application.add_handler(CommandHandler("reminders", reminders_list_command))
    application.add_handler(CommandHandler("delremind", reminders_delete_command))

    # Comandos de IA
    application.add_handler(CommandHandler("ask", ask_command))
    application.add_handler(CommandHandler("askpro", askpro_command))

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

    # Gestión de usuarios (Super Admin)
    application.add_handler(CommandHandler("adduser", adduser_command))
    application.add_handler(CommandHandler("deluser", deluser_command))
    application.add_handler(CommandHandler("listusers", listusers_command))

    # Gestión de archivos
    application.add_handler(CommandHandler("get", get_file_command))
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.ALL, handle_file_upload))

    # <<< INICIO DE LA CORRECCIÓN DE ORDEN >>>

    # --- CONVERSATION HANDLER PARA EL TIEMPO ---
    # Se registra ANTES que el CallbackQueryHandler general para que tenga prioridad.
    weather_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_weather_conversation, pattern='^weather:start$')],
        states={
            AWAITING_LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_weather_location)]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)]
    )
    application.add_handler(weather_conv_handler)

    # Manejador de botones para el resto de los menús interactivos
    # Se registra DESPUÉS para que no intercepte los botones de las conversaciones.
    application.add_handler(CallbackQueryHandler(button_callback_handler))

    # <<< FIN DE LA CORRECCIÓN DE ORDEN >>>

    # TAREAS PERIÓDICAS (Job Queue)
    job_queue = application.job_queue
    check_interval = config.get("monitoring_thresholds", {}).get("check_interval_minutes", 5) * 60
    if check_interval > 0:
        job_queue.run_repeating(periodic_monitoring_check, interval=check_interval, first=10)

    logger.info("El bot se está iniciando...")
    application.run_polling()

if __name__ == "__main__":
    main()
