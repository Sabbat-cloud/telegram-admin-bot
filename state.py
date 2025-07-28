# state.py
# MODULO NUEVO: Carga la configuración y los usuarios una sola vez al inicio.
# El resto de la aplicación importará los datos desde aquí.

import json
import logging
import os
import sys

# --- RUTAS DE FICHEROS ---
BASE_DIR = os.path.dirname(__file__)
CONFIG_FILE = os.path.join(BASE_DIR, 'configbot.json')
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
LOG_STATE_FILE = os.path.join(BASE_DIR, 'log_monitoring_state.json')
SECRETS_FILE = '/etc/telegram-bot/bot.env'
PERSISTENCE_FILE = os.path.join(BASE_DIR, "bot_persistence.json")

# --- FUNCIONES DE CARGA ---

def _cargar_fichero_json(filepath: str, critical: bool = False):
    """Función genérica para cargar ficheros JSON."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        msg = f"Error: El fichero '{filepath}' no se encontró."
        if critical:
            logging.critical(msg)
            sys.exit(1)
        logging.error(msg)
        return {}
    except json.JSONDecodeError:
        msg = f"Error: El fichero '{filepath}' tiene un formato JSON inválido."
        if critical:
            logging.critical(msg)
            sys.exit(1)
        logging.error(msg)
        return {}

def _cargar_secretos(filepath: str):
    """Carga secretos desde un fichero .env seguro."""
    secretos = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                if line.strip() and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    secretos[key.strip()] = value.strip()
        return secretos
    except Exception as e:
        logging.critical(f"ERROR CRÍTICO: No se pudo cargar el fichero de secretos '{filepath}'. Error: {e}")
        sys.exit(1)


# --- DATOS CARGADOS EN MEMORIA ---

# Carga la configuración principal (crítico, si falla el bot se detiene)
CONFIG = _cargar_fichero_json(CONFIG_FILE, critical=True)

# Carga el diccionario de usuarios (no crítico, puede empezar vacío)
USERS_DATA = _cargar_fichero_json(USERS_FILE)

# Carga los secretos (crítico)
SECRETS = _cargar_secretos(SECRETS_FILE)


# --- FUNCIONES PARA MANIPULAR DATOS EN MEMORIA ---

def guardar_usuarios():
    """Guarda el estado actual de USERS_DATA en el fichero."""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(USERS_DATA, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error al guardar usuarios en '{USERS_FILE}': {e}")
        return False

def recargar_configuracion():
    """Recarga la configuración principal en caliente."""
    global CONFIG
    logging.info("Recargando la configuración desde configbot.json...")
    CONFIG = _cargar_fichero_json(CONFIG_FILE, critical=False) or CONFIG

def recargar_usuarios():
    """Recarga los usuarios en caliente."""
    global USERS_DATA
    logging.info("Recargando la lista de usuarios desde users.json...")
    USERS_DATA = _cargar_fichero_json(USERS_FILE) or USERS_DATA

# Verificación inicial de secretos
if "TELEGRAM_TOKEN" not in SECRETS:
    logging.critical("El secreto 'TELEGRAM_TOKEN' no se encontró en el fichero de entorno.")
    sys.exit(1)

