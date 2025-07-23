import requests
import json

# --- CONFIGURACIÓN ---
# Reemplaza esto con el token de tu SabbatuserBot
TOKEN = "7508228283:AAFsyNn36FKLues8AQrqlqA1Lr0kfghH8Qk"
# -------------------

def obtener_actualizaciones():
    """
    Obtiene las últimas actualizaciones recibidas por el bot.
    """
    url_api = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    
    try:
        respuesta = requests.get(url_api, timeout=10)
        
        if respuesta.status_code == 200:
            # Convertimos la respuesta a un formato legible (JSON)
            datos = respuesta.json()
            
            # Imprimimos la respuesta completa para que la veas
            print("--- Respuesta Completa de la API ---")
            print(json.dumps(datos, indent=4))
            print("------------------------------------")

            # Buscamos el Chat ID en el último mensaje
            if datos["ok"] and datos["result"]:
                # Tomamos el chat ID del último mensaje recibido
                chat_id = datos["result"][-1]["message"]["chat"]["id"]
                print(f"\n✅ ¡ÉXITO! Tu Chat ID es: {chat_id}")
                print("\nUsa este número en tu script 'enviar_aviso.py' y vuelve a probarlo.")
            else:
                print("\n❌ No se encontraron mensajes nuevos.")
                print("Asegúrate de haber enviado un mensaje a tu bot (@SabbatuserBot) justo antes de ejecutar este script.")
                
        else:
            print(f"Error al contactar con la API de Telegram: {respuesta.status_code}")
            print(respuesta.text)
            
    except Exception as e:
        print(f"Ocurrió un error: {e}")

# --- EJECUCIÓN ---
if __name__ == "__main__":
    obtener_actualizaciones()
