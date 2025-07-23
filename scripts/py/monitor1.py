import socket
import subprocess
import platform
import requests
import datetime

# Intenta importar psutil, si no está, avisa.
try:
    import psutil
except ImportError:
    # Si el script se ejecuta automáticamente, no veremos este print.
    # El fallo se registrará en el log de cron si está configurado.
    print("Error: La librería 'psutil' no está instalada. Ejecuta: pip install psutil")
    exit()

# --- CONFIGURACIÓN DE TELEGRAM ---
TOKEN_BOT = "7508228283:AAFsyNn36FKLues8AQrqlqA1Lr0kfghH8Qk"
CHAT_ID = "898477137"
# --- CONFIGURACIÓN DE LAS COMPROBACIONES ---
HOSTS_A_VIGILAR = {
    "Servidor Local": "sabbat.localhost",
    "Google DNS": "8.8.8.8",
    # "Otro Servidor": "IP_O_DOMINIO"
}

PUERTOS_A_VIGILAR = {
    "Web (HTTP)": 80,
    "Web (HTTPS)": 443,
    "SSH": 3511,
}

UMBRAL_TEMPERATURA_CPU = 80.0 

# --- FUNCIÓN DE ENVÍO DE TELEGRAM ---
def enviar_reporte_telegram(texto_del_reporte):
    """
    Envía el reporte completo a través del bot de Telegram.
    """
    # Encabezado del mensaje
    nombre_servidor = platform.node() # Obtiene el nombre del host del servidor
    encabezado = f"📋 **Reporte del Servidor: {nombre_servidor}**\n"
    fecha = f"_{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
    
    mensaje_completo = f"{encabezado}\n{texto_del_reporte}\n{fecha}"
    
    url_api = f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': mensaje_completo,
        'parse_mode': 'Markdown'
    }
    try:
        respuesta = requests.post(url_api, data=payload, timeout=10)
        if respuesta.status_code == 200:
            print("Reporte enviado con éxito.")
        else:
            print(f"Error al enviar el reporte: {respuesta.text}")
    except Exception as e:
        print(f"Excepción al enviar el reporte: {e}")

# --- MÓDULOS DE VERIFICACIÓN (MODIFICADOS) ---

def verificar_conexiones(reporte_lines):
    """
    Verifica los hosts y añade el resultado a la lista del reporte.
    """
    reporte_lines.append("\n*-- Conexiones de Red --*")
    for alias, host in HOSTS_A_VIGILAR.items():
        parametro = '-n 1' if platform.system().lower() == 'windows' else '-c 1'
        comando = ['ping', parametro, host]
        try:
            resultado = subprocess.run(comando, capture_output=True, text=True, timeout=5)
            if resultado.returncode == 0:
                reporte_lines.append(f"✅ {alias} ({host}): **Accesible**")
            else:
                reporte_lines.append(f"❌ {alias} ({host}): **INACCESIBLE**")
        except subprocess.TimeoutExpired:
            reporte_lines.append(f"❌ {alias} ({host}): **Timeout (INACCESIBLE)**")

def verificar_puertos(reporte_lines):
    """
    Verifica los puertos y añade el resultado a la lista del reporte.
    """
    reporte_lines.append("\n*-- Estado de Puertos (en este servidor) --*")
    for nombre, puerto in PUERTOS_A_VIGILAR.items():
        try:
            with socket.create_connection(("127.0.0.1", puerto), timeout=3):
                reporte_lines.append(f"✅ Puerto {nombre} ({puerto}): **Abierto**")
        except (socket.timeout, ConnectionRefusedError, OSError):
            reporte_lines.append(f"❌ Puerto {nombre} ({puerto}): **Cerrado**")

def verificar_temperatura(reporte_lines):
    """
    Verifica la temperatura y añade el resultado a la lista del reporte.
    """
    reporte_lines.append("\n*-- Sensores del Sistema --*")
    if not hasattr(psutil, "sensors_temperatures"):
        reporte_lines.append("⚠️ Temperatura CPU: No soportado en este sistema.")
        return

    temps = psutil.sensors_temperatures()
    if 'coretemp' in temps:
        temp_actual = max(entry.current for entry in temps['coretemp'])
        estado = f"✅ Temp. CPU: **{temp_actual:.1f}°C**"
        if temp_actual > UMBRAL_TEMPERATURA_CPU:
            estado = f"🔥 Temp. CPU: **{temp_actual:.1f}°C** (¡ALTA!)"
        reporte_lines.append(estado)
    else:
        reporte_lines.append("⚠️ Temperatura CPU: Sensor no encontrado.")

# --- FUNCIÓN PRINCIPAL ---
def main():
    """
    Orquesta todas las verificaciones y envía el reporte final.
    """
    lineas_del_reporte = []

    # 1. Realizar todas las comprobaciones
    verificar_conexiones(lineas_del_reporte)
    verificar_puertos(lineas_del_reporte)
    verificar_temperatura(lineas_del_reporte)

    # 2. Unir todas las líneas en un solo texto
    reporte_final = "\n".join(lineas_del_reporte)

    # 3. Enviar el reporte por Telegram
    enviar_reporte_telegram(reporte_final)


if __name__ == "__main__":
    main()
