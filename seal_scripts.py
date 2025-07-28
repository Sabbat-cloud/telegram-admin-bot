import json
import hashlib
import os
import shutil
import logging
from datetime import datetime

# --- CONFIGURACIÓN ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
CONFIG_FILE = 'configbot.json'
BACKUP_FILE = f'configbot.json.backup_{datetime.now().strftime("%Y%m%d%H%M%S")}'

def calculate_sha256(filepath):
    """Calcula el hash SHA256 de un fichero, expandiendo la ruta del usuario (~)."""
    expanded_path = os.path.expanduser(filepath)
    sha256_hash = hashlib.sha256()
    try:
        with open(expanded_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        logging.error(f"¡Fichero no encontrado! No se pudo generar el hash para: {expanded_path}")
        return None
    except Exception as e:
        logging.error(f"Error al calcular el hash de {expanded_path}: {e}")
        return None

def safe_seal_scripts():
    """
    Lee configbot.json, calcula el hash de cada script y reescribe el fichero
    de forma segura, preservando toda la configuración existente.
    """
    # --- 1. Crear copia de seguridad ---
    try:
        shutil.copyfile(CONFIG_FILE, BACKUP_FILE)
        logging.info(f"Copia de seguridad creada en: {BACKUP_FILE}")
    except FileNotFoundError:
        logging.error(f"Error: El fichero de configuración '{CONFIG_FILE}' no existe. Abortando.")
        return

    # --- 2. Leer el fichero JSON completo en memoria ---
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        logging.error(f"Error al leer o decodificar '{CONFIG_FILE}'. Restaura desde la copia de seguridad si es necesario.")
        return

    # --- 3. Modificar solo la sección de scripts en memoria ---
    scripts_to_update = config_data.get("scripts", {})
    if not scripts_to_update:
        logging.error(f"Error: No se encontró la clave 'scripts' en '{CONFIG_FILE}' o está vacía.")
        return

    update_count = 0
    for script_name, script_info in scripts_to_update.items():
        path = script_info.get("path")
        if not path:
            logging.warning(f"Saltando script '{script_name}' porque no tiene una clave 'path'.")
            continue

        logging.info(f"Procesando script: '{script_name}'")
        current_hash = calculate_sha256(path)

        if current_hash:
            script_info['sha256_hash'] = current_hash
            update_count += 1
            logging.info(f" -> Hash actualizado: {current_hash[:12]}...")

    # --- 4. Reescribir el fichero completo con los datos actualizados ---
    if update_count > 0:
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=2)
            logging.info(f"\n✅ ¡Éxito! Se han actualizado los hashes de {update_count} scripts en '{CONFIG_FILE}'.")
            logging.info("El resto de tu configuración se ha conservado intacta.")
        except Exception as e:
            logging.error(f"¡ERROR CRÍTICO AL ESCRIBIR! No se pudo guardar el fichero '{CONFIG_FILE}'. Error: {e}")
            logging.error("Por favor, restaura el fichero desde la copia de seguridad.")
    else:
        logging.info("\nNo se realizaron cambios. Revisa los errores o warnings anteriores.")


if __name__ == "__main__":
    print("=========================================================")
    print("== Script de Sellado de Seguridad (Versión Segura)     ==")
    print("=========================================================")
    print(f"Este script actualizará los hashes en '{CONFIG_FILE}' sin borrar el resto de la configuración.")
    
    try:
        input("Pulsa Enter para continuar o CTRL+C para cancelar...")
        safe_seal_scripts()
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
