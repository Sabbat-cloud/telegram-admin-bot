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

# Directorios donde se buscarán nuevos scripts.
# Puedes añadir más rutas si organizas tus scripts de otra forma.
SCRIPT_DIRECTORIES = [
    'scripts/py',
    'scripts/sh',
    'scripts/sh/backup' # Añadido para los backups
]

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

def discover_and_seal_scripts():
    """
    Descubre nuevos scripts, los añade a la configuración y sella todos
    los scripts (nuevos y existentes) con su hash SHA256.
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

    # --- 3. Descubrir nuevos scripts ---
    if "scripts" not in config_data:
        config_data["scripts"] = {}
    
    scripts_in_config = config_data["scripts"]
    new_scripts_found = 0

    logging.info("--- Buscando nuevos scripts ---")
    for script_dir in SCRIPT_DIRECTORIES:
        if not os.path.isdir(script_dir):
            logging.warning(f"El directorio '{script_dir}' no existe, se omitirá.")
            continue
            
        for filename in os.listdir(script_dir):
            if filename.endswith(".py") or filename.endswith(".sh"):
                script_name = os.path.splitext(filename)[0]
                
                if script_name not in scripts_in_config:
                    new_scripts_found += 1
                    script_path = os.path.join(script_dir, filename)
                    scripts_in_config[script_name] = {
                        "path": script_path,
                        "description": f"Script {script_name}",
                        "sha256_hash": "" # Se calculará en el siguiente paso
                    }
                    logging.info(f" -> Nuevo script encontrado: '{script_name}' en '{script_path}'")

    if new_scripts_found > 0:
        logging.info(f"Se encontraron {new_scripts_found} scripts nuevos que se añadirán a la configuración.")
    else:
        logging.info("No se encontraron scripts nuevos.")

    # --- 4. Actualizar hashes de TODOS los scripts (nuevos y existentes) ---
    logging.info("\n--- Actualizando hashes de seguridad (sellado) ---")
    update_count = 0
    for script_name, script_info in scripts_in_config.items():
        path = script_info.get("path")
        if not path:
            logging.warning(f"Saltando script '{script_name}' porque no tiene una clave 'path'.")
            continue

        logging.info(f"Procesando: '{script_name}'")
        current_hash = calculate_sha256(path)

        if current_hash:
            if script_info.get("sha256_hash") != current_hash:
                script_info['sha256_hash'] = current_hash
                update_count += 1
                logging.info(f" -> Hash actualizado: {current_hash[:12]}...")
            else:
                logging.info(" -> Hash sin cambios.")

    # --- 5. Reescribir el fichero completo con los datos actualizados ---
    if update_count > 0 or new_scripts_found > 0:
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config_data, f, indent=2, sort_keys=True)
            logging.info(f"\n✅ ¡Éxito! '{CONFIG_FILE}' actualizado.")
            logging.info(f"   - {new_scripts_found} scripts añadidos.")
            logging.info(f"   - {update_count} hashes actualizados.")
        except Exception as e:
            logging.error(f"¡ERROR CRÍTICO AL ESCRIBIR! No se pudo guardar el fichero '{CONFIG_FILE}'. Error: {e}")
            logging.error("Por favor, restaura el fichero desde la copia de seguridad.")
    else:
        logging.info("\nNo se realizaron cambios en el fichero de configuración.")


if __name__ == "__main__":
    print("================================================================")
    print("== Script de Sellado y Detección Automática de Scripts        ==")
    print("================================================================")
    print(f"Este script buscará nuevos scripts, los añadirá a '{CONFIG_FILE}'")
    print("y actualizará los hashes de seguridad de todos los scripts.")
    
    try:
        input("\nPulsa Enter para continuar o CTRL+C para cancelar...")
        discover_and_seal_scripts()
    except KeyboardInterrupt:
        print("\nOperación cancelada por el usuario.")
