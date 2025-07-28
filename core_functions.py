# core_functions.py
# MODIFICADO: Contiene la lógica composición de reportes y llamadas a APIs.

import json
import socket
import platform
import datetime
import logging
import os
import ssl
import psutil
import re
import google.generativeai as genai
import time
import subprocess

# Los módulos de estado y utilidades de sistema se importan ahora
from state import CONFIG, USERS_DATA, guardar_usuarios, LOG_STATE_FILE, SECRETS
from system_utils import get_log_lines, search_log_in_file, fail2ban_status_cmd, fail2ban_unban_cmd, _run_command

# --- Chequeos individuales (ping, puerto, SSL) ---

def check_ping(host: str, _):
    param = '-n 1' if platform.system().lower() == 'windows' else '-c 1'
    try:
        result = subprocess.run(['ping', param, host], capture_output=True, text=True, timeout=5)
        return "✅ Ping: **Accesible**" if result.returncode == 0 else "❌ Ping: **INACCESIBLE**"
    except subprocess.TimeoutExpired:
        return "❌ Ping: **Timeout**"

def check_port(host: str, port_name: str, port_num: int, _):
    try:
        with socket.create_connection((host, port_num), timeout=3):
            return f"✅ Puerto {port_name} ({port_num}): **Abierto**"
    except (socket.timeout, ConnectionRefusedError, OSError):
        return f"❌ Puerto {port_name} ({port_num}): **Cerrado**"

def check_ssl_expiry(host: str, port: int, days_warning: int, _):
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                expiry_date = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                days_left = (expiry_date - datetime.datetime.now()).days
                if days_left > days_warning:
                    return f"✅ Cert. SSL: Expira en **{days_left} días**"
                return f"🔥 Cert. SSL: Expira en **{days_left} días** (Aviso a los {days_warning})"
    except Exception as e:
        logging.warning(f"Error SSL para {host}: {e}")
        return "❌ Cert. SSL: **No se pudo verificar**"

# --- Composición de Reportes y Textos ---

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
    reporte_data = {}
    for servidor in CONFIG.get("servidores", []):
        nombre_servidor = servidor.get("nombre", "Servidor sin nombre")
        host = servidor.get("host")
        if not host: continue
        
        reporte_data[nombre_servidor] = []
        chequeos = servidor.get("chequeos", {})
        if chequeos.get("ping"):
            reporte_data[nombre_servidor].append(check_ping(host, _))
        if "puertos" in chequeos:
            for nombre_puerto, num_puerto in chequeos["puertos"].items():
                reporte_data[nombre_servidor].append(check_port(host, nombre_puerto, num_puerto, _))
        if "certificado_ssl" in chequeos:
            params = chequeos["certificado_ssl"]
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

def get_system_info_text(_) -> str:
    try:
        uname_output = subprocess.run(['uname', '-a'], capture_output=True, text=True, timeout=5, check=True).stdout
        lsb_output = ""
        try:
            lsb_output = subprocess.run(['lsb_release', '-a'], capture_output=True, text=True, timeout=5, check=True).stdout
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass # No es un error crítico si lsb_release no está
        
        response = _("ℹ️ **Información del Sistema**:\n```\n{output}\n```\n").format(output=uname_output)
        if lsb_output and "No LSB modules are available" not in lsb_output:
            response += _("📦 *Distribución:*\n```\n{output}\n```").format(output=lsb_output)
        else:
            response += _("📦 *Distribución: No se encontró `lsb_release`.*")
        return response
    except Exception as e:
        return _("❌ Error inesperado al obtener info del sistema: {error}").format(error=e)

def get_cron_tasks(_) -> str:
    try:
        proc = subprocess.run('crontab -l', shell=True, capture_output=True, text=True, timeout=10)
        if proc.stderr and "no crontab for" in proc.stderr:
            return _("ℹ️ No hay tareas de cron configuradas para el usuario actual.")
        elif proc.returncode != 0:
            return _("❌ **Error al leer crontab:**\n`{error}`").format(error=proc.stderr)
        return _("🗓️ **Tareas de Cron (`crontab -l`):**\n\n```\n{output}\n```").format(output=proc.stdout or '(Vacío)')
    except Exception as e:
        return _("❌ **Error inesperado** al consultar cron: {error}").format(error=e)

def get_service_status(service_name: str, _):
    try:
        proc = subprocess.run(['systemctl', 'status', service_name], capture_output=True, text=True, timeout=10)
        output = proc.stdout + proc.stderr
        status_icon, status_text = ("✅", "Activo") if "active (running)" in output else \
                                   ("❌", "Inactivo") if "inactive (dead)" in output else \
                                   ("🔥", "Ha fallado") if "failed" in output else \
                                   ("❔", "Desconocido")
        
        log_lines = re.findall(r'●.*|Loaded:.*|Active:.*|Main PID:.*|(?<=─ ).*', output)
        detalle = "\n".join(log_lines[-5:])
        return _("{icon} **Estado de `{p}`: {txt}**\n\n```\n{det}\n```").format(icon=status_icon, p=service_name, txt=_(status_text), det=detalle or _('No hay detalles.'))
    except Exception as e:
        return _("❌ Error al verificar {p}: {e}").format(p=service_name, e=e)


# --- Lógica de Comandos ---

def get_log_content(log_alias: str, num_lines: int, _) -> str:
    log_path = CONFIG.get("allowed_logs", {}).get(log_alias)
    if not log_path:
        return _("❌ El log '{alias}' no está permitido.").format(alias=log_alias)
    
    success, output = get_log_lines(log_path, num_lines)
    if success:
        return _("📜 **Últimas {num_lines} líneas de `{alias}`:**\n```\n{output}\n```").format(num_lines=num_lines, alias=log_alias, output=output or _("(El log está vacío)"))
    return _("❌ Error al leer el log {alias}:\n```\n{output}\n```").format(alias=log_alias, output=output)

def search_log(log_alias: str, pattern: str, _) -> str:
    # CORREGIDO: Bug Crítico. La variable log_path no estaba definida.
    log_path = CONFIG.get("allowed_logs", {}).get(log_alias)
    if not log_path:
        return _("❌ El log '{alias}' no está permitido.").format(alias=log_alias)

    success, output = search_log_in_file(log_path, pattern)
    if not success:
        return _("❌ Error al buscar en {alias}: {error}").format(alias=log_alias, error=output)
    
    if not output:
        return _("🔍 No se encontraron coincidencias para '{pattern}' en `{alias}`.").format(pattern=pattern, alias=log_alias)

    return _("🔍 **Resultados para '{pattern}' en `{alias}`:**\n```\n{output}\n```").format(pattern=pattern, alias=log_alias, output=output)
    
def manage_service(service_name: str, action: str, _) -> str:
    allowed_services = CONFIG.get("servicios_permitidos", [])
    if service_name not in allowed_services:
        return _("❌ El servicio '{service_name}' no está en la lista de servicios permitidos.").format(service_name=service_name)
    
    command = ['sudo', 'systemctl', action, service_name]
    # Usamos la función genérica de system_utils
    success, output = _run_command(command, 30)

    if not success:
        return _("❌ Error al ejecutar la acción '{action}' en '{service_name}':\n```\n{output}\n```").format(action=action, service_name=service_name, output=output)

    # Esperamos un momento y obtenemos el estado final
    time.sleep(2)
    final_status = get_service_status(service_name, _)
    
    action_map_past = {'start': "iniciado", 'stop': "parado", 'restart': "reiniciado"}
    success_msg = _("✅ **Servicio `{service_name}` {action_past_tense} con éxito.**").format(service_name=service_name, action_past_tense=_(action_map_past.get(action)))
    
    return f"{success_msg}\n\n{final_status}"

def ask_gemini_model(prompt: str, model_name: str, _) -> str:
    gemini_config = CONFIG.get("gemini_api", {})
    if not gemini_config.get("enabled"):
        return _("❌ La función de consulta a la API de Gemini no está habilitada.")
    
    api_key = SECRETS.get("GEMINI_API_KEY")
    if not api_key:
        return _("❌ La API Key de Gemini no está configurada en el fichero de secretos.")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)
        if response.parts:
            return _("🤖 **Respuesta ({model_name}):**\n\n{text}").format(model_name=model_name.split('/')[-1], text=response.text)
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

def docker_logic(action: str, _, container_name: str = None, num_lines: int = 20) -> str:
    """Lógica para gestionar los comandos de Docker."""
    docker_allowed = CONFIG.get("docker_containers_allowed", [])

    if action == 'ps':
        success, output = _run_command(['docker', 'ps', '--format', 'table {{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Ports}}'], 20)
        if success:
            return _("🐳 **Contenedores Docker Activos:**\n```\n{output}\n```").format(output=output)
        return _("❌ Error al listar contenedores:\n```\n{output}\n```").format(output=output)

    if not container_name:
        return _("❌ Se requiere el nombre del contenedor para esta acción.")

    if container_name not in docker_allowed:
        return _("❌ El contenedor '{container_name}' no está permitido.").format(container_name=container_name)

    if action == 'logs':
        success, output = _run_command(['docker', 'logs', '--tail', str(num_lines), container_name], 60)
        if success:
            return _("📜 **Logs de `{container_name}` (últimas {num_lines} líneas):**\n```\n{output}\n```").format(container_name=container_name, num_lines=num_lines, output=output)
        return _("❌ Error al obtener logs de {container_name}:\n```\n{output}\n```").format(container_name=container_name, output=output)
    
    elif action == 'restart':
        success, output = _run_command(['sudo', 'docker', 'restart', container_name], 30)
        if success:
            return _("🔄 **Contenedor `{container_name}` Reiniciado:**\n```\n{output}\n```").format(container_name=container_name, output=output or "Comando ejecutado.")
        return _("❌ Error al reiniciar {container_name}:\n```\n{output}\n```").format(container_name=container_name, output=output)
        
    return _("❌ Acción de Docker no reconocida.")

def fail2ban_status(_, jail=None):
    success, output = fail2ban_status_cmd(jail)
    if success:
        clean_output = output.replace("`-", "").replace("|-", "").strip()
        return _("🛡️ **Estado de Fail2Ban**:\n```\n{output}\n```").format(output=clean_output)
    return _("❌ Error al obtener estado de Fail2Ban: `{error}`").format(error=output)

def fail2ban_unban(ip: str, _):
    jails = CONFIG.get('fail2ban_jails', [])
    if not jails:
        return _("⚠️ No hay jaulas de Fail2Ban definidas en la configuración.")
    
    results = []
    for jail in jails:
        success, output = fail2ban_unban_cmd(jail, ip)
        if success and "unbanned" in output:
            results.append(_("✅ IP `{ip}` desbloqueada de la jaula `{jail}`.").format(ip=ip, jail=jail))
    
    if not results:
        return _("ℹ️ La IP `{ip}` no parece estar baneada en ninguna de las jaulas configuradas.").format(ip=ip)
    return "\n".join(results)


# --- Monitorización de Logs ---
def _load_log_state():
    if not os.path.exists(LOG_STATE_FILE): return {}
    try:
        with open(LOG_STATE_FILE, 'r') as f: return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError): return {}

def _save_log_state(state):
    try:
        with open(LOG_STATE_FILE, 'w') as f: json.dump(state, f, indent=2)
    except Exception as e:
        logging.error(f"CRITICAL: No se pudo guardar el estado de monitorización de logs: {e}")

def check_watched_logs(_):
    log_config = CONFIG.get('log_monitoring', {})
    if not log_config.get('enabled', False): return []

    log_paths = CONFIG.get('allowed_logs', {})
    state = _load_log_state()
    alerts = []

    for watched_log in log_config.get('watched_logs', []):
        alias, patterns = watched_log.get('alias'), watched_log.get('patterns', [])
        log_path = log_paths.get(alias)
        if not log_path or not patterns: continue

        if alias not in state: state[alias] = {'last_pos': 0, 'inode': 0}

        try:
            stat_info = os.stat(log_path)
            if stat_info.st_ino != state[alias].get('inode', 0) or stat_info.st_size < state[alias].get('last_pos', 0):
                state[alias]['last_pos'] = 0
            state[alias]['inode'] = stat_info.st_ino

            with open(log_path, 'r', errors='ignore') as f:
                f.seek(state[alias]['last_pos'])
                for line in f:
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            alerts.append(_("🚨 **Alerta de Log en `{alias}`**:\n\n```\n{line}\n```").format(alias=alias, line=line.strip()))
                            break
                state[alias]['last_pos'] = f.tell()
        except FileNotFoundError:
            logging.warning(f"Log no encontrado para monitorización: {log_path}")
        except Exception as e:
            logging.error(f"Error al procesar el log {alias}: {e}")

    _save_log_state(state)
    return alerts
