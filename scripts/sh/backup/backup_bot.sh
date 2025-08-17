#!/bin/bash

# --- CONFIGURACIÓN ---
# Directorio home
SOURCE_DIR="$HOME/telegram/"

# Directorio donde se guardarán los archivos de backup.
# Es MUY recomendable que sea un directorio fuera del de origen. Otra particionm.
BACKUP_DIR="$HOME/backups"

# --- LÓGICA DEL SCRIPT ---

# 1. Crea el directorio de backups si no existe.
# El parámetro -p asegura que no dé error si el directorio ya existe.
echo "Asegurando que el directorio de destino existe: ${BACKUP_DIR}"
mkdir -p ${BACKUP_DIR}

# 2. Genera un nombre de archivo único con la fecha y hora actual.
# Formato: DDMMYYYYHHMMSS
TIMESTAMP=$(date +"%d%m%Y%H%M%S")
FILENAME="backup-bot${TIMESTAMP}.tar.gz"

# 3. Muestra un mensaje de inicio.
echo "Iniciando backup de ${SOURCE_DIR}..."
echo "Destino: ${BACKUP_DIR}/${FILENAME}"

# 4. Usa el comando 'tar' para crear el archivo comprimido.
#    -c: Crea un nuevo archivo.
#    -z: Comprime el archivo usando gzip (.tar.gz).
#    -v: Modo "verbose", muestra los archivos que se están procesando.
#    -f: Especifica el nombre del archivo de salida.
tar -czvf "${BACKUP_DIR}/${FILENAME}" -C $(dirname ${SOURCE_DIR}) $(basename ${SOURCE_DIR})

# 5. Muestra un mensaje de finalización.
echo "-------------------------------------"
echo "✅ Backup finalizado con éxito."
echo "Archivo guardado en: ${BACKUP_DIR}/${FILENAME}"
