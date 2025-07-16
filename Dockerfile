# Imagen oficial de Python ligera.
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instala las dependencias del sistema (nmap y traceroute)
# Se limpian las listas de apt para mantener la imagen pequeña
RUN apt-get update && \
    apt-get install -y --no-install-recommends nmap traceroute && \
    rm -rf /var/lib/apt/lists/*

# Copia primero el fichero de requisitos para aprovechar el caché de Docker
COPY requirements.txt .

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de tu proyecto al directorio de trabajo
COPY . .

# Comando que se ejecutará cuando el contenedor se inicie
CMD ["python3", "bot/bot.py"]
