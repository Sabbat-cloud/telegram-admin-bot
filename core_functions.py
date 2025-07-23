# core_functions.py
# Contiene la lógica las funciones de "trabajo pesado".
# No tiene dependencias de la librería de Telegram.

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

# --- CARGA Y GUARDADO DE CONFIGURACIÓN ---
def cargar_configuracion():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: El archivo de configuración '{CONFIG_FILE}' no se encontró.")
        sys.exit()
    except json.JSONDecodeError:
        logging.error(f"Error: El archivo de configuración '{CONFIG_FILE}' tiene un formato JSON inválido.")
        sys.exit()

def guardar_configuracion(config_data):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        return True
    except Exception as e:
        logging.error(f"Error al guardar la configuración en '{CONFIG_FILE}': {e}")
        return False

# --- LÓGICA DE VERIFICACIÓN ---
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
                expiry_date = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z') # <--- CORREGIDO
                days_left = (expiry_date - datetime.datetime.now()).days # <--- CORREGIDO
                if days_left > days_warning:
                    return _("✅ Cert. SSL: Expira en **{days_left} días**").format(days_left=days_left)
                return _("🔥 Cert. SSL: Expira en **{days_left} días** (Aviso a los {days_warning})").format(days_left=days_left, days_warning=days_warning)
    except Exception as e:
        logging.warning(f"Error SSL para {host}: {e}")
        return _("❌ Cert. SSL: **No se pudo verificar**")

# --- GENERACIÓN DE REPORTES ---
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
    fecha = _("\n_{datetime}_").format(datetime=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')) # <--- CORREGIDO
    lineas_reporte.append(fecha)
    return "\n".join(lineas_reporte)

# --- FUNCIONES DE RED ---
def _run_command(command, timeout, success_msg, error_msg_prefix, _):
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
        output = proc.stdout or proc.stderr
        if len(output) > 4000:
            output = output[:4000] + "\n\n... (salida truncada)"
        return f"{success_msg}\n```\n{output}\n```"
    except FileNotFoundError:
        return _("❌ Error: El comando `{command}` no se encuentra. ¿Está instalado?").format(command=command[0])
    except subprocess.TimeoutExpired:
        return _("❌ Error: Timeout ({timeout}s) durante la ejecución de `{command}`.").format(timeout=timeout, command=command[0])
    except Exception as e:
        return f"❌ {error_msg_prefix}: {e}"

def do_ping(host: str, _) -> str:
    param = '-n 4' if platform.system().lower() == 'windows' else '-c 4'
    return _run_command(['ping', param, host], 20, _("📡 **Resultado de Ping a `{host}`:**").format(host=host), _("Error inesperado de ping"), _)

def do_traceroute(host: str, _) -> str:
    command = ['traceroute', '-w', '2', host]
    return _run_command(command, 60, _("🗺️ **Resultado de Traceroute a `{host}`:**").format(host=host), _("Error inesperado de traceroute"), _)

def do_nmap(host: str, _) -> str:
    return _run_command(['nmap', '-A', host], 600, _("🔬 **Resultado de Nmap -A a `{host}`:**").format(host=host), _("Error inesperado de Nmap"), _)

def do_dig(domain: str, _) -> str:
    return _run_command(['dig', domain], 30, _("🌐 **Resultado de DIG para `{domain}`:**").format(domain=domain), _("Error inesperado de DIG"), _)

def do_whois(domain: str, _) -> str:
    return _run_command(['whois', domain], 30, _("👤 **Resultado de WHOIS para `{domain}`:**").format(domain=domain), _("Error inesperado de WHOIS"), _)

# --- FUNCIONES DE ADMINISTRACIÓN Y MONITOREO DEL SISTEMA ---
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

def search_log(log_alias: str, pattern: str, _) -> str:
    config = cargar_configuracion()
    log_path = config.get("allowed_logs", {}).get(log_alias)
    if not log_path:
        return _("❌ El log '{alias}' no está permitido.").format(alias=log_alias)
    try:
        proc = subprocess.run(['grep', '-i', pattern, log_path], capture_output=True, text=True, timeout=60)
        if proc.returncode == 1:
            return _("🔍 No se encontraron coincidencias para '{pattern}' en `{alias}`.").format(pattern=pattern, alias=log_alias)
        output = proc.stdout
        if len(output) > 4000:
            output = output[:3900] + "\n... (salida truncada)"
        return _("🔍 **Resultados para '{pattern}' en `{alias}`:**\n```\n{output}\n```").format(pattern=pattern, alias=log_alias, output=output)
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

def get_fortune_text(_) -> str:
    """Ejecuta el comando 'fortune' y devuelve su salida formateada."""
    try:
        proc = subprocess.run(['/usr/games/fortune'], capture_output=True, text=True, timeout=5, check=True)
        return _("🍀 **Tu fortuna dice:**\n\n```\n{fortune}\n```").format(fortune=proc.stdout)
    except FileNotFoundError:
        return _("❌ Error: El comando `fortune` no se encuentra. ¿Está instalado en el servidor?")
    except Exception as e:
        return _("❌ Error inesperado al ejecutar fortune: {error}").format(error=e)

# --- FUNCIONES DE IA (GEMINI API) ---

def ask_gemini_model(prompt: str, model_name: str, _) -> str:
    """
    Envía un prompt a un modelo de Gemini especificado y devuelve su respuesta.
    """
    config = cargar_configuracion()
    gemini_config = config.get("gemini_api", {})

    if not gemini_config.get("enabled"):
        return _("❌ La función de consulta a la API de Gemini no está habilitada.")

    api_key = gemini_config.get("api_key")
    if not api_key or "AQUÍ_VA_TU_API_KEY" in api_key:
        return _("❌ La API Key de Gemini no está configurada en `configbot.json`.")

    try:
        # Configura la API
        genai.configure(api_key=api_key)

        # Crea el modelo y genera la respuesta
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)

        # Extraer el texto de la respuesta
        if response.parts:
            return _("🤖 **Respuesta ({model_name}):**\n\n{text}").format(model_name=model_name.split('/')[-1], text=response.text)
        else:
            # Esto puede ocurrir si la respuesta fue bloqueada por seguridad
            return _("❌ No se recibió una respuesta válida del modelo. La solicitud pudo haber sido bloqueada por políticas de seguridad.")

    except Exception as e:
        logging.error(f"Error al contactar con la API de Gemini: {e}")
        return _("❌ Ocurrió un error al procesar la consulta con Gemini: `{error}`").format(error=str(e))

# --- RECORDATORIOS ---
def parse_time_to_seconds(time_str: str) -> int:
    """
    Parsea un string de tiempo como "1h 30m 15s" a segundos.
    Soporta días (d), horas (h), minutos (m) y segundos (s).
    Devuelve 0 si el formato es inválido.
    """
    parts = re.findall(r'(\d+)\s*([dhms])', time_str.lower())
    if not parts:
        return 0

    delta_args = {"days": 0, "hours": 0, "minutes": 0, "seconds": 0}
    for value, unit in parts:
        if unit == 'd':
            delta_args['days'] += int(value)
        elif unit == 'h':
            delta_args['hours'] += int(value)
        elif unit == 'm':
            delta_args['minutes'] += int(value)
        elif unit == 's':
            delta_args['seconds'] += int(value)

    return int(datetime.timedelta(**delta_args).total_seconds()) # <--- CORREGIDO

def get_weather_text(location: str, _) -> str:
    """
    Ejecuta ansiweather para una localidad y devuelve el resultado sin códigos de color.
    """
    command = ['ansiweather', '-l', location]
    try:
        # Usamos subprocess.run directamente para controlar mejor la salida
        proc = subprocess.run(command, capture_output=True, text=True, timeout=15, check=True)
        # Eliminamos los códigos de color ANSI de la salida para que se vea bien en Telegram
        cleaned_output = re.sub(r'\x1b\[[0-9;]*m', '', proc.stdout)

        return _("☀️ **El tiempo en {location}:**\n```\n{weather_data}\n```").format(
            location=location.title(),
            weather_data=cleaned_output.strip()
        )
    except FileNotFoundError:
        return _("❌ Error: El comando `ansiweather` no se encuentra. Por favor, instálalo en el servidor.")
    except subprocess.CalledProcessError as e:
        # Esto puede ocurrir si la ciudad no se encuentra
        error_output = re.sub(r'\x1b\[[0-9;]*m', '', e.stderr or e.stdout)
        return _("❌ Error al obtener el tiempo para `{location}`:\n```\n{error}\n```").format(location=location, error=error_output.strip())
    except Exception as e:
        logging.error(f"Error inesperado al ejecutar ansiweather: {e}")
        return _("❌ Error inesperado al obtener el tiempo: {error}").format(error=str(e))
