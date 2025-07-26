# core_functions.py
# Contiene la lógica las funciones de "trabajo pesado".

import json
import socket
import subprocess
import platform
import datetime
import logging
import os
import sys
import ssl
import psutil
import time
import re
import google.generativeai as genai

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'configbot.json')
USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')
LOG_STATE_FILE = os.path.join(os.path.dirname(__file__), 'log_monitoring_state.json')

def cargar_secretos():
    """Carga secretos desde un fichero .env seguro."""
    secretos = {}
    try:
        # Apuntamos directamente a tu fichero bot.env
        with open('/etc/telegram-bot/bot.env', 'r') as f:
            for line in f:
                # Ignoramos comentarios y líneas en blanco
                if line.strip() and not line.strip().startswith('#'):
                    # Dividimos la línea por el primer '=' que encuentre
                    key, value = line.strip().split('=', 1)
                    secretos[key] = value
        return secretos
    except Exception as e:
        logging.critical(f"ERROR CRÍTICO: No se pudo cargar el fichero de secretos '/etc/telegram-bot/bot.env'. Error: {e}")
        return None
# --- CARGA Y GUARDADO DE CONFIGURACIÓN Y USUARIOS ---
def cargar_configuracion():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: El archivo de configuración '{CONFIG_FILE}' no se encontró.")
        sys.exit(1)
    except json.JSONDecodeError:
        logging.error(f"Error: El archivo de configuración '{CONFIG_FILE}' tiene un formato JSON inválido.")
        sys.exit(1)

def cargar_usuarios():
    try:
        with open(USERS_FILE, 'r') as f:
            users_data = json.load(f)
            logging.info(f"[LOAD_USERS] Fichero 'users.json' cargado. Super admin: {users_data.get('super_admin_id')}")
            return users_data
    except FileNotFoundError:
        logging.error(f"Error: El archivo de usuarios '{USERS_FILE}' no se encontró.")
        return {}
    except json.JSONDecodeError:
        logging.error(f"Error: El archivo de usuarios '{USERS_FILE}' es inválido.")
        return {}

def guardar_usuarios(users_data):
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users_data, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error al guardar usuarios en '{USERS_FILE}': {e}")
        return False

# --- FUNCIONES DE COMANDOS DE SISTEMA (SINCRÓNICAS) ---

def _run_command(command, timeout, success_msg, error_msg_prefix, _):
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        output = proc.stdout or proc.stderr
        if proc.returncode != 0 and "INACCESIBLE" not in success_msg:
             return f"❌ {error_msg_prefix}: {output or '(Sin salida de error)'}"
        if len(output) > 4000:
            output = output[:4000] + "\n\n... (salida truncada)"
        return f"{success_msg}\n```\n{output}\n```"
    except FileNotFoundError:
        return _("❌ Error: El comando `{command}` no se encuentra. ¿Está instalado?").format(command=command[0])
    except subprocess.TimeoutExpired:
        return _("❌ Error: Timeout ({timeout}s) durante la ejecución de `{command}`.").format(timeout=timeout, command=command[0])
    except Exception as e:
        return f"❌ {error_msg_prefix}: {e}"

def run_shell_script(script_name: str, _):
    config = cargar_configuracion()
    script_path_raw = config.get("scripts_permitidos", {}).get(script_name)
    if not script_path_raw: return _("❌ Script no encontrado o no permitido.")
    script_path = os.path.expanduser(script_path_raw)
    return _run_command([script_path], 120, _("✅ **Script '{name}' ejecutado:**").format(name=script_name), _("Error al ejecutar {name}").format(name=script_name), _)

def run_python_script(script_name: str, _):
    config = cargar_configuracion()
    script_path_raw = config.get("python_scripts_permitidos", {}).get(script_name)
    if not script_path_raw: return _("❌ Script no encontrado o no permitido.")
    script_path = os.path.expanduser(script_path_raw)
    return _run_command([sys.executable, script_path], 300, _("✅ **Script '{name}' ejecutado:**").format(name=script_name), _("Error al ejecutar {name}").format(name=script_name), _)

def get_cron_tasks(_):
    try:
        proc = subprocess.run('crontab -l', shell=True, capture_output=True, text=True, timeout=10)
        if proc.stderr and "no crontab for" in proc.stderr:
            return _("ℹ️ No hay tareas de cron configuradas para el usuario actual.")
        elif proc.returncode != 0:
            return _("❌ **Error al leer crontab:**\n`{error}`").format(error=proc.stderr)
        else:
            return _("🗓️ **Tareas de Cron (`crontab -l`):**\n\n```\n{output}\n```").format(output=proc.stdout or '(Vacío)')
    except Exception as e:
        return _("❌ **Error inesperado** al consultar cron: {error}").format(error=e)

def get_service_status(service_name: str, _):
    try:
        proc = subprocess.run(['systemctl', 'status', service_name], capture_output=True, text=True, timeout=10)
        output = proc.stdout + proc.stderr
        status_icon, status_text = (_("✅"), _("Activo")) if "active (running)" in output else \
                                   (_("❌"), _("Inactivo")) if "inactive (dead)" in output else \
                                   (_("🔥"), _("Ha fallado")) if "failed" in output else \
                                   (_("❔"), _("Desconocido"))
        log_lines = re.findall(r'●.*|Loaded:.*|Active:.*|Main PID:.*|(?<=─ ).*', output)
        detalle = "\n".join(log_lines[-5:])
        return _("{icon} **Estado de `{p}`: {txt}**\n\n```\n{det}\n```").format(icon=status_icon, p=service_name, txt=status_text, det=detalle or _('No hay detalles.'))
    except Exception as e:
        return _("❌ Error al verificar {p}: {e}").format(p=service_name, e=e)

def check_ping(host, _):
    param = '-n 1' if platform.system().lower() == 'windows' else '-c 1'
    command = ['ping', param, host]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        return _("✅ Ping: **Accesible**") if result.returncode == 0 else _("❌ Ping: **INACCESIBLE**")
    except subprocess.TimeoutExpired:
        return _("❌ Ping: **Timeout**")

def check_port(host, port_name, port_num, _):
    try:
        with socket.create_connection((host, port_num), timeout=3):
            return _("✅ Puerto {port_name} ({port_num}): **Abierto**").format(port_name=port_name, port_num=port_num)
    except (socket.timeout, ConnectionRefusedError, OSError):
        return _("❌ Puerto {port_name} ({port_num}): **Cerrado**").format(port_name=port_name, port_num=port_num)

def check_ssl_expiry(host, port, days_warning, _):
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                expiry_date = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                days_left = (expiry_date - datetime.datetime.now()).days
                if days_left > days_warning:
                    return _("✅ Cert. SSL: Expira en **{days_left} días**").format(days_left=days_left)
                return _("🔥 Cert. SSL: Expira en **{days_left} días** (Aviso a los {days_warning})").format(days_left=days_left, days_warning=days_warning)
    except Exception as e:
        logging.warning(f"Error SSL para {host}: {e}")
        return _("❌ Cert. SSL: **No se pudo verificar**")

def get_resources_text(_):
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        load_avg_text = ""
        if hasattr(psutil, 'getloadavg'):
            cpu_load = psutil.getloadavg()
            load_avg_text = _("Carga media (1, 5, 15 min): `{load1:.2f}`, `{load5:.2f}`, `{load15:.2f}`\n").format(load1=cpu_load[0], load5=cpu_load[1], load15=cpu_load[2])
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        return (
            _("💻 **Reporte de Recursos del Sistema**\n\n") +
            _("--- **CPU** ---\n") +
            _("Uso actual: `{cpu_percent}%`\n").format(cpu_percent=cpu_percent) +
            load_avg_text +
            _("--- **Memoria (RAM)** ---\n") +
            _("Uso: `{ram_used:.2f} GB` de `{ram_total:.2f} GB` (*{ram_percent}%*)\n\n").format(ram_used=ram.used / (1024**3), ram_total=ram.total / (1024**3), ram_percent=ram.percent) +
            _("--- **Disco Principal (/)** ---\n") +
            _("Uso: `{disk_used:.2f} GB` de `{disk_total:.2f} GB` (*{disk_percent}%*)").format(disk_used=disk.used / (1024**3), disk_total=disk.total / (1024**3), disk_percent=disk.percent)
        )
    except Exception as e:
        logging.error(f"Error inesperado en get_resources_text con psutil: {e}")
        return _("❌ **Error inesperado al obtener recursos:** {error}").format(error=e)

def get_status_report_text(_):
    config = cargar_configuracion()
    reporte_data = {}
    for servidor in config.get("servidores", []):
        nombre_servidor = servidor.get("nombre", "Servidor sin nombre")
        host = servidor.get("host")
        if not host: continue
        reporte_data[nombre_servidor] = []
        if servidor.get("chequeos", {}).get("ping"):
            reporte_data[nombre_servidor].append(check_ping(host, _))
        if "puertos" in servidor.get("chequeos", {}):
            for nombre_puerto, num_puerto in servidor["chequeos"]["puertos"].items():
                reporte_data[nombre_servidor].append(check_port(host, nombre_puerto, num_puerto, _))
        if "certificado_ssl" in servidor.get("chequeos", {}):
            params = servidor["chequeos"]["certificado_ssl"]
            reporte_data[nombre_servidor].append(check_ssl_expiry(host, params.get("puerto", 443), params.get("dias_aviso", 30), _))
    nombre_maquina_local = platform.node()
    encabezado = _("📋 **Reporte de Estado (desde {hostname})**\n").format(hostname=nombre_maquina_local)
    lineas_reporte = [encabezado]
    for servidor, checks in reporte_data.items():
        lineas_reporte.append(f"\n--- **{servidor}** ---")
        lineas_reporte.extend(checks)
    fecha = _("\n_{datetime}_").format(datetime=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    lineas_reporte.append(fecha)
    return "\n".join(lineas_reporte)

def do_ping(host: str, _) -> str:
    param = '-n 4' if platform.system().lower() == 'windows' else '-c 4'
    return _run_command(['ping', param, host], 20, _("📡 **Resultado de Ping a `{host}`:**").format(host=host), _("Error inesperado de ping"), _)

def do_traceroute(host: str, _) -> str:
    command = ['traceroute', '-w', '2', host]
    return _run_command(command, 60, _("🗺️ **Resultado de Traceroute a `{host}`:**").format(host=host), _("Error inesperado de traceroute"), _)

def do_nmap(host: str, _) -> str:
    # Timeout reducido de 600 a 180 segundos
    return _run_command(['nmap', '-A', host], 180, _("🔬 **Resultado de Nmap -A a `{host}`:**").format(host=host), _("Error inesperado de Nmap"), _)

def do_dig(domain: str, _) -> str:
    return _run_command(['dig', domain], 30, _("🌐 **Resultado de DIG para `{domain}`:**").format(domain=domain), _("Error inesperado de DIG"), _)

def do_whois(domain: str, _) -> str:
    return _run_command(['whois', domain], 30, _("👤 **Resultado de WHOIS para `{domain}`:**").format(domain=domain), _("Error inesperado de WHOIS"), _)

def get_disk_usage_text(_) -> str:
    return _run_command(['df', '-h'], 10, _("💾 **Uso de Disco (`df -h`)**"), _("Error al ejecutar `df -h`"), _)

def get_processes_text(_) -> str:
    return _run_command(['ps', 'aux'], 30, _("⚙️ **Procesos (`ps aux`)**"), _("Error al ejecutar `ps aux`"), _)

def get_system_info_text(_) -> str:
    try:
        uname_output = subprocess.run(['uname', '-a'], capture_output=True, text=True, timeout=5, check=True).stdout
        lsb_output = ""
        try:
            lsb_output = subprocess.run(['lsb_release', '-a'], capture_output=True, text=True, timeout=5, check=True).stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass
        response = _("ℹ️ **Información del Sistema**:\n```\n{output}\n```\n").format(output=uname_output)
        if lsb_output and "No LSB modules are available" not in lsb_output:
            response += _("📦 *Distribución:*\n```\n{output}\n```").format(output=lsb_output)
        else:
            response += _("📦 *Distribución: No se encontró `lsb_release`.*")
        return response
    except Exception as e:
        return _("❌ Error inesperado al obtener info del sistema: {error}").format(error=e)

def get_log_lines(log_alias: str, num_lines: int, _) -> str:
    config = cargar_configuracion()
    log_path = config.get("allowed_logs", {}).get(log_alias)
    if not log_path:
        return _("❌ El log '{alias}' no está permitido.").format(alias=log_alias)
    return _run_command(['tail', '-n', str(num_lines), log_path], 30, _("📜 **Últimas {num_lines} líneas de `{alias}`:**").format(num_lines=num_lines, alias=log_alias), _("Error al leer el log {alias}").format(alias=log_alias), _)


def is_safe_grep_pattern(pattern: str) -> bool:
    """
    Valida que un patrón de búsqueda para grep sea seguro.
    """
    if not pattern or len(pattern) > 100: # Limita la longitud
        return False
    # Patrón que prohíbe metacaracteres complejos de regex como `+` o `*` que pueden causar ReDoS.
    # Permite solo caracteres alfanuméricos, espacios, puntos, guiones, etc.
    if re.search(r'[\\*+?(){}|\[\]\^$]', pattern):
         logging.warning(f"Patrón de búsqueda bloqueado por contener metacaracteres peligrosos: {pattern}")
         return False
    return True

# Se ha modificado la función search_log para hacerla segura.
def search_log(log_alias: str, pattern: str, _) -> str:
    if not is_safe_grep_pattern(pattern):
        return _("❌ El patrón de búsqueda contiene caracteres no permitidos o es demasiado complejo.")    
    try:
        # Se añade el argumento '--' antes del patrón del usuario.
        # Esto le indica a 'grep' que todo lo que sigue es un argumento posicional (el patrón de búsqueda)
        # y no una opción, previniendo así la inyección de argumentos como '-f /etc/passwd'.
        command = ['grep', '-i', '--', pattern, log_path]
        
        # Mantenemos un timeout generoso, ya que la búsqueda puede ser lenta.
        proc = subprocess.run(command, capture_output=True, text=True, timeout=60)
        
        if proc.returncode == 1:
            return _("🔍 No se encontraron coincidencias para '{pattern}' en `{alias}`.").format(pattern=pattern, alias=log_alias)
        
        output = proc.stdout
        if len(output) > 4000:
            output = output[:3900] + "\n... (salida truncada)"
            
        return _("🔍 **Resultados para '{pattern}' en `{alias}`:**\n```\n{output}\n```").format(pattern=pattern, alias=log_alias, output=output)
    except subprocess.TimeoutExpired:
        return _("❌ Error: Timeout (60s) durante la búsqueda en el log `{alias}`.").format(alias=log_alias)
    except Exception as e:
        return _("❌ Error inesperado al buscar en {alias}: {error}").format(alias=log_alias, error=e)

def docker_command(action: str, _, container_name: str = None, num_lines: int = 10) -> str:
    config = cargar_configuracion()
    docker_allowed = config.get("docker_containers_allowed", [])
    if action == 'ps':
        return _run_command(['docker', 'ps', '--format', 'table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}'], 20, _("🐳 **Contenedores Docker Activos:**"), _("Error al listar contenedores"), _)
    if not container_name:
        return _("❌ Se requiere el nombre del contenedor para esta acción.")
    if container_name not in docker_allowed:
        return _("❌ El contenedor '{container_name}' no está permitido.").format(container_name=container_name)
    if action == 'logs':
        return _run_command(['docker', 'logs', '--tail', str(num_lines), container_name], 60, _("📜 **Logs de `{container_name}` (últimas {num_lines} líneas):**").format(container_name=container_name, num_lines=num_lines), _("Error al obtener logs de {container_name}").format(container_name=container_name), _)
    elif action == 'restart':
        return _run_command(['sudo', 'docker', 'restart', container_name], 30, _("🔄 **Contenedor `{container_name}` Reiniciado:**").format(container_name=container_name), _("Error al reiniciar {container_name}").format(container_name=container_name), _)
    return _("❌ Acción de Docker no reconocida.")

def manage_service(service_name: str, action: str, _) -> str:
    config = cargar_configuracion()
    allowed_services = config.get("servicios_permitidos", [])
    if service_name not in allowed_services:
        return _("❌ El servicio '{service_name}' no está en la lista de servicios permitidos.").format(service_name=service_name)
    command = ['sudo', 'systemctl', action, service_name]
    action_map_present = {'start': _("Iniciando"), 'stop': _("Parando"), 'restart': _("Reiniciando")}
    action_map_past = {'start': _("iniciado"), 'stop': _("parado"), 'restart': _("reiniciado")}
    action_text = action_map_present.get(action, action.capitalize())
    success_msg = _("✅ **Servicio `{service_name}` {action_past_tense} con éxito.**").format(service_name=service_name, action_past_tense=action_map_past.get(action))
    error_msg_prefix = _("❌ Error al {action_text} el servicio '{service_name}'").format(action_text=action_text.lower(), service_name=service_name)
    execution_result = _run_command(command, 30, success_msg, error_msg_prefix, _)
    time.sleep(2)
    status_report = get_service_status(service_name, _)
    final_status_line = status_report.split('\n', 1)[0]
    return execution_result.split('```')[0] + f"```{final_status_line}```"

def get_fortune_text(_) -> str:
    try:
        proc = subprocess.run(['/usr/games/fortune'], capture_output=True, text=True, timeout=5, check=True)
        return _("🍀 **Tu fortuna dice:**\n\n```\n{fortune}\n```").format(fortune=proc.stdout)
    except FileNotFoundError:
        return _("❌ Error: El comando `fortune` no se encuentra. ¿Está instalado en el servidor?")
    except Exception as e:
        return _("❌ Error inesperado al ejecutar fortune: {error}").format(error=e)

def ask_gemini_model(prompt: str, model_name: str, _) -> str:
    config = cargar_configuracion()
    gemini_config = config.get("gemini_api", {})
    if not gemini_config.get("enabled"):
        return _("❌ La función de consulta a la API de Gemini no está habilitada.")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _("❌ La API Key de Gemini no está configurada en la variable de entorno `GEMINI_API_KEY`.")
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)
        if response.parts:
            return _("🤖 **Respuesta ({model_name}):**\n\n{text}").format(model_name=model_name.split('/')[-1], text=response.text)
        else:
            return _("❌ No se recibió una respuesta válida del modelo. La solicitud pudo haber sido bloqueada.")
    except Exception as e:
        logging.error(f"Error al contactar con la API de Gemini: {e}")
        return _("❌ Ocurrió un error al procesar la consulta con Gemini: `{error}`").format(error=str(e))

def parse_time_to_seconds(time_str: str) -> int:
    parts = re.findall(r'(\d+)\s*([dhms])', time_str.lower())
    if not parts: return 0
    delta_args = {"days": 0, "hours": 0, "minutes": 0, "seconds": 0}
    for value, unit in parts:
        if unit == 'd': delta_args['days'] += int(value)
        elif unit == 'h': delta_args['hours'] += int(value)
        elif unit == 'm': delta_args['minutes'] += int(value)
        elif unit == 's': delta_args['seconds'] += int(value)
    return int(datetime.timedelta(**delta_args).total_seconds())

def get_weather_text(location: str, _) -> str:
    command = ['ansiweather', '-l', location]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=15, check=True)
        cleaned_output = re.sub(r'\x1b\[[0-9;]*m', '', proc.stdout)
        return _("☀️ **El tiempo en {location}:**\n```\n{weather_data}\n```").format(location=location.title(), weather_data=cleaned_output.strip())
    except FileNotFoundError:
        return _("❌ Error: El comando `ansiweather` no se encuentra. Por favor, instálalo en el servidor.")
    except subprocess.CalledProcessError as e:
        error_output = re.sub(r'\x1b\[[0-9;]*m', '', e.stderr or e.stdout)
        return _("❌ Error al obtener el tiempo para `{location}`:\n```\n{error}\n```").format(location=location, error=error_output.strip())
    except Exception as e:
        logging.error(f"Error inesperado al ejecutar ansiweather: {e}")
        return _("❌ Error inesperado al obtener el tiempo: {error}").format(error=str(e))

def run_backup_script(script_name: str, _) -> str:
    config = cargar_configuracion()
    script_path = config.get("backup_scripts", {}).get(script_name)
    if not script_path:
        return _("❌ El script de backup '{name}' no está permitido o no existe.").format(name=script_name)
    script_path = os.path.expanduser(script_path)
    if not os.path.exists(script_path):
         return _("❌ Error: La ruta del script '{path}' no existe en el servidor.").format(path=script_path)
    # Los backups pueden tardar, 900s (15min) es un timeout razonable que se controlará con el lock.
    return _run_command([script_path], 900, _("✅ **Backup '{name}' finalizado con éxito:**").format(name=script_name), _("❌ **Error al ejecutar el backup '{name}':**").format(name=script_name), _)

# --- NUEVAS FUNCIONES PARA FAIL2BAN ---
def fail2ban_status(_, jail=None):
    command = ['sudo', 'fail2ban-client', 'status']
    if jail:
        command.append(jail)
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=20, check=True)
        output = proc.stdout.replace("`-", "").replace("|-", "").strip()
        return _("🛡️ **Estado de Fail2Ban**:\n```\n{output}\n```").format(output=output)
    except subprocess.CalledProcessError as e:
        return _("❌ Error al obtener estado de Fail2Ban: `{error}`").format(error=e.stderr)
    except Exception as e:
        return _("❌ Error inesperado con Fail2Ban: {error}").format(error=e)

def fail2ban_unban(ip: str, _):
    config = cargar_configuracion()
    jails = config.get('fail2ban_jails', [])
    if not jails:
        return _("⚠️ No hay jaulas de Fail2Ban definidas en `configbot.json`.")
    results = []
    for jail in jails:
        command = ['sudo', 'fail2ban-client', 'set', jail, 'unbanip', ip]
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=15, check=True)
            if "unbanned" in proc.stdout:
                results.append(_("✅ IP `{ip}` desbloqueada de la jaula `{jail}`.").format(ip=ip, jail=jail))
        except subprocess.CalledProcessError:
            continue
        except Exception as e:
            results.append(_("❌ Error al intentar desbloquear en `{jail}`: {error}").format(jail=jail, error=e))
    if not results:
        return _("ℹ️ La IP `{ip}` no parece estar baneada en ninguna de las jaulas configuradas.").format(ip=ip)
    return "\n".join(results)

# --- NUEVAS FUNCIONES PARA MONITORIZACIÓN DE LOGS ---
def _load_log_state():
    if not os.path.exists(LOG_STATE_FILE):
        return {}
    try:
        with open(LOG_STATE_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}

def _save_log_state(state):
    try:
        with open(LOG_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logging.error(f"CRITICAL: No se pudo guardar el estado de monitorización de logs en {LOG_STATE_FILE}. Las alertas se repetirán. Verifique los permisos del fichero. Error: {e}")

def check_watched_logs(_):
    config = cargar_configuracion()
    log_config = config.get('log_monitoring', {})
    if not log_config.get('enabled', False):
        return []

    log_paths = config.get('allowed_logs', {})
    state = _load_log_state()
    alerts = []

    for watched_log in log_config.get('watched_logs', []):
        alias = watched_log.get('alias')
        patterns = watched_log.get('patterns', [])
        log_path = log_paths.get(alias)

        if not log_path or not patterns:
            continue

        if alias not in state:
            state[alias] = {'last_pos': 0, 'inode': 0}

        try:
            stat_info = os.stat(log_path)
            current_inode = stat_info.st_ino
            current_size = stat_info.st_size

            last_inode = state[alias].get('inode', 0)
            last_pos = state[alias].get('last_pos', 0)

            if current_inode != last_inode or current_size < last_pos:
                last_pos = 0
                state[alias]['inode'] = current_inode

            with open(log_path, 'r', errors='ignore') as f:
                f.seek(last_pos)
                new_lines = f.readlines()
                state[alias]['last_pos'] = f.tell()

                for line in new_lines:
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            alert_msg = _("🚨 **Alerta de Log en `{alias}`**:\n\n```\n{line}\n```").format(alias=alias, line=line.strip())
                            alerts.append(alert_msg)
                            break
        except FileNotFoundError:
            logging.warning(f"Log no encontrado para monitorización: {log_path}")
            continue
        except Exception as e:
            logging.error(f"Error al procesar el log {alias}: {e}")

    _save_log_state(state)
    return alerts
