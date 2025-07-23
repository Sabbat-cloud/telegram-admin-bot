import socket
import subprocess
import platform
import requests
import datetime

# Intenta importar psutil, si no está, avisa.
try:
    import psutil
except ImportError:
    print("Error: La librería 'psutil' no está instalada. Ejecuta: pip install psutil")
    exit()

# --- CONFIGURACIÓN DE TELEGRAM ---
TOKEN_BOT = "7508228283:AAFsyNn36FKLues8AQrqlqA1Lr0kfghH8Qk"
CHAT_ID = "898477137"
# --- CONFIGURACIÓN CENTRALIZADA DE SERVIDORES ---
# Aquí defines todos los servidores y qué comprobar en cada uno.
# Puedes añadir o quitar diccionarios de esta lista.
SERVIDORES_A_MONITORIZAR = [
    {
        "nombre": "Servidor Principal ",
        "host": "sabbat.cloud", # Usa 127.0.0.1 para la máquina local
        "comprobar_ping": True,
        "puertos": {
            "Web (HTTP)": 80,
            "Web (HTTPS)": 443,
            "SSH": 3511
        },
        "comprobar_temperatura": True,
        "umbral_temperatura": 80.0
    },
    {
        "nombre": "Bienes Muebles Alicante",
        "host": "rbmalicante.es", # IP o dominio del otro servidor
        "comprobar_ping": True,
        "puertos": {
            "Web (HTTP)": 80,
            "Web (HTTPS)": 443,
        },
        "comprobar_temperatura": False # No podemos medir temps de forma remota
    },
    {
        "nombre": "DNS de Google (Prueba Conectividad)",
        "host": "8.8.8.8",
        "comprobar_ping": True,
        "puertos": {}, # No comprobamos puertos aquí
        "comprobar_temperatura": False
    }
]

# --- FUNCIÓN DE ENVÍO DE TELEGRAM ---
def enviar_reporte_telegram(texto_del_reporte):
    """
    Envía el reporte completo a través del bot de Telegram.
    """
    nombre_maquina_local = platform.node()
    encabezado = f"📋 **Reporte de Monitorización (desde {nombre_maquina_local})**\n"
    fecha = f"_{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_"
    
    mensaje_completo = f"{encabezado}\n{texto_del_reporte}\n\n{fecha}"
    
    url_api = f"https://api.telegram.org/bot{TOKEN_BOT}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': mensaje_completo,
        'parse_mode': 'Markdown'
    }
    try:
        requests.post(url_api, data=payload, timeout=10)
        print("Reporte enviado con éxito.")
    except Exception as e:
        print(f"Excepción al enviar el reporte: {e}")

# --- MÓDULOS DE VERIFICACIÓN (AHORA RECIBEN LA CONFIGURACIÓN) ---

def verificar_ping(host):
    """Verifica si un host está accesible haciendo ping."""
    parametro = '-n 1' if platform.system().lower() == 'windows' else '-c 1'
    comando = ['ping', parametro, host]
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=5)
        return "✅ **Accesible**" if resultado.returncode == 0 else "❌ **INACCESIBLE**"
    except subprocess.TimeoutExpired:
        return "❌ **Timeout**"

def verificar_puerto(host, puerto):
    """Verifica si un puerto TCP está abierto en un host."""
    try:
        with socket.create_connection((host, puerto), timeout=3):
            return "✅ Abierto"
    except (socket.timeout, ConnectionRefusedError, OSError):
        return "❌ Cerrado"

def verificar_temperatura(umbral):
    """Verifica la temperatura de la CPU local."""
    if not hasattr(psutil, "sensors_temperatures"):
        return "⚠️ No soportado"

    temps = psutil.sensors_temperatures()
    if 'coretemp' in temps:
        temp_actual = max(entry.current for entry in temps['coretemp'])
        estado = f"✅ {temp_actual:.1f}°C"
        if temp_actual > umbral:
            estado = f"🔥 **{temp_actual:.1f}°C** (¡ALTA!)"
        return estado
    return "⚠️ Sensor no encontrado"

# --- FUNCIÓN PRINCIPAL ---
def main():
    """
    Orquesta todas las verificaciones para cada servidor configurado.
    """
    reporte_final_lines = []

    for servidor in SERVIDORES_A_MONITORIZAR:
        nombre_servidor = servidor["nombre"]
        host_servidor = servidor["host"]
        
        reporte_final_lines.append(f"\n--- **{nombre_servidor}** ({host_servidor}) ---")

        # 1. Comprobar Ping (si está activado)
        if servidor.get("comprobar_ping", False):
            resultado_ping = verificar_ping(host_servidor)
            reporte_final_lines.append(f"Conexión: {resultado_ping}")

        # 2. Comprobar Puertos (si hay puertos definidos)
        if "puertos" in servidor and servidor["puertos"]:
            for nombre_puerto, num_puerto in servidor["puertos"].items():
                resultado_puerto = verificar_puerto(host_servidor, num_puerto)
                reporte_final_lines.append(f"· Puerto {nombre_puerto} ({num_puerto}): {resultado_puerto}")

        # 3. Comprobar Temperatura (si está activado y es la máquina local)
        if servidor.get("comprobar_temperatura", False):
            if host_servidor == "127.0.0.1" or host_servidor == "localhost":
                umbral = servidor.get("umbral_temperatura", 80.0)
                resultado_temp = verificar_temperatura(umbral)
                reporte_final_lines.append(f"Temperatura CPU: {resultado_temp}")
            else:
                # Nota: No podemos medir temperaturas de hosts remotos con este método.
                pass
    
    # Enviar el reporte final
    enviar_reporte_telegram("\n".join(reporte_final_lines))

if __name__ == "__main__":
    main()
