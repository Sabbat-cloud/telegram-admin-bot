# system_utils.py
# MODULO NUEVO: Contiene funciones de bajo nivel para ejecutar comandos del sistema.

import subprocess
import logging
import re
import hashlib
import os

def _run_command(command: list, timeout: int) -> tuple[bool, str]:
    """
    Ejecuta un comando de sistema y devuelve un tuple (éxito, salida).
    """
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False  # No lanzar excepción en códigos de retorno distintos de 0
        )
        output = proc.stdout or proc.stderr
        
        # Truncar salida si es muy larga
        if len(output) > 4000:
            output = output[:4000] + "\n\n... (salida truncada)"
            
        return proc.returncode == 0, output.strip()

    except FileNotFoundError:
        return False, f"Error: El comando '{command[0]}' no se encuentra. ¿Está instalado?"
    except subprocess.TimeoutExpired:
        return False, f"Error: Timeout ({timeout}s) durante la ejecución de '{' '.join(command)}'."
    except Exception as e:
        logging.error(f"Excepción en _run_command con '{' '.join(command)}': {e}")
        return False, f"Error inesperado: {e}"

def do_ping(host: str, _) -> str:
    # El _ es un placeholder para la función de traducción, no se usa aquí.
    success, output = _run_command(['ping', '-c', '4', host], 20)
    if success:
        return _("📡 **Resultado de Ping a `{host}`:**\n```\n{output}\n```").format(host=host, output=output)
    return _("❌ **Error de Ping a `{host}`:**\n```\n{output}\n```").format(host=host, output=output)

def do_traceroute(host: str, _) -> str:
    success, output = _run_command(['traceroute', '-w', '2', host], 60)
    if success:
        return _("🗺️ **Resultado de Traceroute a `{host}`:**\n```\n{output}\n```").format(host=host, output=output)
    return _("❌ **Error de Traceroute a `{host}`:**\n```\n{output}\n```").format(host=host, output=output)

def do_nmap(host: str, _) -> str:
    success, output = _run_command(['nmap', '-A', host], 180)
    if success:
        return _("🔬 **Resultado de Nmap -A a `{host}`:**\n```\n{output}\n```").format(host=host, output=output)
    return _("❌ **Error de Nmap a `{host}`:**\n```\n{output}\n```").format(host=host, output=output)

def do_dig(domain: str, _) -> str:
    success, output = _run_command(['dig', domain], 30)
    if success:
        return _("🌐 **Resultado de DIG para `{domain}`:**\n```\n{output}\n```").format(domain=domain, output=output)
    return _("❌ **Error de DIG para `{domain}`:**\n```\n{output}\n```").format(domain=domain, output=output)

def do_whois(domain: str, _) -> str:
    success, output = _run_command(['whois', domain], 30)
    if success:
        return _("👤 **Resultado de WHOIS para `{domain}`:**\n```\n{output}\n```").format(domain=domain, output=output)
    return _("❌ **Error de WHOIS para `{domain}`:**\n```\n{output}\n```").format(domain=domain, output=output)

def get_disk_usage_text(_) -> str:
    success, output = _run_command(['df', '-h'], 10)
    if success:
        return _("💾 **Uso de Disco (`df -h`)**\n```\n{output}\n```").format(output=output)
    return _("❌ **Error al ejecutar `df -h`:**\n```\n{output}\n```").format(output=output)

def get_processes_text(_) -> str:
    success, output = _run_command(['ps', 'aux'], 30)
    if success:
        return _("⚙️ **Procesos (`ps aux`)**\n```\n{output}\n```").format(output=output)
    return _("❌ **Error al ejecutar `ps aux`:**\n```\n{output}\n```").format(output=output)

def get_log_lines(log_path: str, num_lines: int) -> tuple[bool, str]:
    return _run_command(['tail', '-n', str(num_lines), log_path], 30)

def search_log_in_file(log_path: str, pattern: str) -> tuple[bool, str]:
    command = ['grep', '-i', '--', pattern, log_path]
    success, output = _run_command(command, 60)
    # Grep devuelve 1 si no hay coincidencias, no es un error.
    if not success and "timeout" not in output.lower() and "no se encuentra" not in output.lower():
        return True, "" # No encontrado
    return success, output

def fail2ban_status_cmd(jail=None) -> tuple[bool, str]:
    command = ['sudo', 'fail2ban-client', 'status']
    if jail:
        command.append(jail)
    return _run_command(command, 20)

def fail2ban_unban_cmd(jail: str, ip: str) -> tuple[bool, str]:
    command = ['sudo', 'fail2ban-client', 'set', jail, 'unbanip', ip]
    return _run_command(command, 15)

def get_fortune_text_cmd(_) -> str:
    success, output = _run_command(['/usr/games/fortune'], 5)
    if success:
        return _("🍀 **Tu fortuna dice:**\n\n```\n{fortune}\n```").format(fortune=output)
    return _("❌ Error: El comando `fortune` no se encuentra o ha fallado.")

def get_weather_text_cmd(location: str, _) -> str:
    success, output = _run_command(['ansiweather', '-l', location], 15)
    
    # Primero, comprueba si el comando tuvo éxito.
    if success:
        # Si tuvo éxito, limpia los códigos de color y devuelve el resultado.
        cleaned_output = re.sub(r'\x1b\[[0-9;]*m', '', output)
        return _("☀️ **El tiempo en {location}:**\n```\n{weather_data}\n```").format(location=location.title(), weather_data=cleaned_output.strip())
    
    # Si el comando falló, el 'output' ya es el mensaje de error.
    # No es necesario limpiarlo.
    return _("❌ Error al obtener el tiempo para `{location}`:\n```\n{error}\n```").format(location=location, error=output.strip())

def _calculate_sha256(filepath):
    """Calcula el hash SHA256 de un fichero."""
    sha256_hash = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    except FileNotFoundError:
        return None
def run_script(script_type: str, script_name: str, _):
    """
    Ejecuta un script de forma segura y devuelve la salida como texto plano.
    """
    from state import CONFIG

    script_info = CONFIG.get("scripts", {}).get(script_name)
    if not script_info or not script_info.get("path"):
        return _("❌ Script no encontrado o no permitido.")

    script_path = os.path.expanduser(script_info["path"])
    stored_hash = script_info.get("sha256_hash")

    if not stored_hash:
        return _("🛡️ ERROR DE SEGURIDAD: El script '{name}' no tiene hash. Ejecución abortada.").format(name=script_name)

    current_hash = _calculate_sha256(script_path)
    if not current_hash:
        return _("❌ Error: No se pudo encontrar o leer el fichero del script en: {path}").format(path=script_path)

    if current_hash != stored_hash:
        logging.critical(f"ALERTA DE SEGURIDAD: Hash de '{script_name}' no coincide. Esperado: {stored_hash}, Actual: {current_hash}")
        return _("🛡️ ALERTA DE SEGURIDAD: La firma del script '{name}' ha cambiado. Ejecución bloqueada.").format(name=script_name)
    
    command = [script_path]
    if script_type == "python":
        import sys
        command.insert(0, sys.executable)
    
    success, output = _run_command(command, 300)
    
    # --- FORMATO DE TEXTO PLANO mejorar en prox version ---
    if success:
        return f"✅ Script '{script_name}' ejecutado:\n\n--- INICIO DE LA SALIDA ---\n{output or '(Sin salida)'}\n--- FIN DE LA SALIDA ---"
    else:
        return f"❌ Error al ejecutar '{script_name}':\n\n--- INICIO DEL ERROR ---\n{output}\n--- FIN DEL ERROR ---"

# --- NUEVAS FUNCIONES PARA LOS SCRIPTS EXTERNOS ---
def run_analizador_logs(args: list, _):
    """Ejecuta el script analizador_logs."""
    command = ['/usr/local/bin/analizador_logs'] + args
    success, output = _run_command(command, 120)
    return output

def run_muestra(args: list, _):
    """Ejecuta el script muestra."""
    command = ['/usr/local/bin/muestra'] + args
    success, output = _run_command(command, 20)
    return output

def run_muestrared(args: list, _):
    """Ejecuta el script muestrared."""
    command = ['/usr/local/bin/muestrared'] + args
    success, output = _run_command(command, 30)
    return output

def run_redes(args: list, _):
    """Ejecuta el script redes."""
    command = ['/usr/local/bin/redes'] + args
    success, output = _run_command(command, 180)
    return output
