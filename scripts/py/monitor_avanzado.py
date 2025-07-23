import json
import socket
import subprocess
import platform
import requests
import datetime
import logging
import os
import ssl

# --- CONFIGURACIÓN DEL LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='monitor.log',
    filemode='a'
)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logging.getLogger('').addHandler(console)

# --- RUTAS DE ARCHIVOS ---
CONFIG_FILE = 'config.json'
STATUS_FILE = 'status.json'

# --- FUNCIONES DE UTILIDAD ---
def cargar_configuracion():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Error: El archivo de configuración '{CONFIG_FILE}' no se encontró.")
        exit()
    except json.JSONDecodeError:
        logging.error(f"Error: El archivo de configuración '{CONFIG_FILE}' tiene un formato JSON inválido.")
        exit()

def cargar_estado_anterior():
    if not os.path.exists(STATUS_FILE):
        return {}
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError):
        return {}

def guardar_estado_actual(estado):
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(estado, f, indent=4)
    except IOError as e:
        logging.error(f"No se pudo escribir en el archivo de estado '{STATUS_FILE}': {e}")

def enviar_mensaje_telegram(mensaje, config_telegram):
    url_api = f"https://api.telegram.org/bot{config_telegram['token']}/sendMessage"
    payload = {
        'chat_id': config_telegram['chat_id'],
        'text': mensaje,
        'parse_mode': 'Markdown'
    }
    try:
        requests.post(url_api, data=payload, timeout=10)
        logging.info("Mensaje enviado a Telegram.")
    except Exception as e:
        logging.error(f"Excepción al enviar mensaje a Telegram: {e}")

def formatear_y_enviar_reporte(reporte_data, config_telegram):
    """Formatea y envía el reporte periódico completo."""
    nombre_maquina_local = platform.node()
    encabezado = f"📋 **Reporte de Estado (desde {nombre_maquina_local})**\n"
    lineas_reporte = [encabezado]

    for servidor, checks in reporte_data.items():
        lineas_reporte.append(f"\n--- **{servidor}** ---")
        for check in checks:
            lineas_reporte.append(check)
    
    fecha = f"\n_{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
    lineas_reporte.append(fecha)
    
    mensaje_completo = "\n".join(lineas_reporte)
    enviar_mensaje_telegram(mensaje_completo, config_telegram)

# --- MÓDULOS DE VERIFICACIÓN (SIN CAMBIOS) ---
def check_ping(host):
    param = '-n 1' if platform.system().lower() == 'windows' else '-c 1'
    command = ['ping', param, host]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return "OK", f"✅ Ping: **Accesible**"
        return "FALLO", f"❌ Ping: **INACCESIBLE**"
    except subprocess.TimeoutExpired:
        return "FALLO", f"❌ Ping: **Timeout**"

def check_port(host, port_name, port_num):
    try:
        with socket.create_connection((host, port_num), timeout=3):
            return "OK", f"✅ Puerto {port_name} ({port_num}): **Abierto**"
    except (socket.timeout, ConnectionRefusedError, OSError):
        return "FALLO", f"❌ Puerto {port_name} ({port_num}): **Cerrado**"

def check_disk_usage(path, threshold):
    try:
        usage = psutil.disk_usage(path)
        if usage.percent < threshold:
            return "OK", f"✅ Disco '{path}': **{usage.percent}%** usado"
        return "FALLO", f"🔥 Disco '{path}': **{usage.percent}%** usado (Umbral: {threshold}%)"
    except (FileNotFoundError, psutil.Error):
        return "FALLO", f"❌ Disco '{path}': **Error al verificar**"

def check_ssl_expiry(host, port, days_warning):
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=5) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                expiry_date = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                days_left = (expiry_date - datetime.datetime.now()).days
                if days_left > days_warning:
                    return "OK", f"✅ Cert. SSL: Expira en **{days_left} días**"
                return "FALLO", f"🔥 Cert. SSL: Expira en **{days_left} días** (Aviso a los {days_warning})"
    except Exception as e:
        logging.warning(f"Error SSL para {host}: {e}")
        return "FALLO", f"❌ Cert. SSL: **No se pudo verificar**"

# --- MOTOR PRINCIPAL ---
def main():
    logging.info("--- Iniciando ciclo de monitorización ---")
    config = cargar_configuracion()
    estado_anterior = cargar_estado_anterior()
    estado_actual = {}
    reporte_data_completo = {}

    for servidor in config.get("servidores", []):
        nombre_servidor = servidor.get("nombre", "Servidor sin nombre")
        host = servidor.get("host")
        if not host: continue
        
        reporte_data_completo[nombre_servidor] = []

        for tipo_chequeo, params in servidor.get("chequeos", {}).items():
            if not params: continue

            if tipo_chequeo == "ping":
                check_id = f"{nombre_servidor}_ping_{host}"
                status, message = check_ping(host)
                estado_actual[check_id] = status
                reporte_data_completo[nombre_servidor].append(message)
            
            elif tipo_chequeo == "puertos":
                for nombre_puerto, num_puerto in params.items():
                    check_id = f"{nombre_servidor}_port_{num_puerto}"
                    status, message = check_port(host, nombre_puerto, num_puerto)
                    estado_actual[check_id] = status
                    reporte_data_completo[nombre_servidor].append(message)
            
            elif tipo_chequeo == "uso_disco" and (host == "127.0.0.1" or host == platform.node()):
                for path, disk_params in params.items():
                    check_id = f"{nombre_servidor}_disk_{path.replace('/', '_')}"
                    status, message = check_disk_usage(path, disk_params["umbral"])
                    estado_actual[check_id] = status
                    reporte_data_completo[nombre_servidor].append(message)

            elif tipo_chequeo == "certificado_ssl":
                check_id = f"{nombre_servidor}_ssl_{host}"
                status, message = check_ssl_expiry(host, params.get("puerto", 443), params.get("dias_aviso", 30))
                estado_actual[check_id] = status
                reporte_data_completo[nombre_servidor].append(message)

    # Comparar estados y enviar alertas de CAMBIOS
    for check_id, status_actual in estado_actual.items():
        status_previo = estado_anterior.get(check_id, "OK")
        
        # Formatear mensaje para alertas
        # (check_id viene como "Nombre Servidor_tipo_detalle")
        partes_id = check_id.split('_')
        nombre_alerta = f"En **{partes_id[0]}**, el chequeo **{' '.join(partes_id[1:])}**"

        if status_actual == "FALLO" and status_previo == "OK":
            mensaje_alerta = f"🚨 **FALLO DETECTADO**\n\n{nombre_alerta} ha comenzado a fallar."
            enviar_mensaje_telegram(mensaje_alerta, config["telegram"])
        elif status_actual == "OK" and status_previo == "FALLO":
            mensaje_alerta = f"✅ **SERVICIO RECUPERADO**\n\n{nombre_alerta} ha vuelto a funcionar correctamente."
            enviar_mensaje_telegram(mensaje_alerta, config["telegram"])

    # Enviar el reporte periódico si está activado
    if config.get("telegram", {}).get("enviar_reporte_periodico", False):
        formatear_y_enviar_reporte(reporte_data_completo, config["telegram"])

    guardar_estado_actual(estado_actual)
    logging.info("--- Ciclo de monitorización finalizado ---")

if __name__ == "__main__":
    try:
        import psutil
        main()
    except ImportError:
        logging.error("La librería 'psutil' es necesaria. Por favor, instálala con: pip install psutil")
