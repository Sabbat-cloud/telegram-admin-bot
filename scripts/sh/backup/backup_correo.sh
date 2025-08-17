#!/bin/bash

# ==============================================================================
# Script para respaldar la configuración de un servidor de correo en Debian
# Autor: sabbat.cloud
# Fecha: 16-08-2025
# ==============================================================================

# --- Variables de Configuración ---

# Directorio principal donde se guardarán los backups
# La virgulilla (~) se expandirá a tu directorio home (ej: /home/sabbat)
DEST_DIR="~/backups/backupcorreo"

# Formato de fecha para el nombre del fichero de backup
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Nombre del fichero final
ARCHIVE_NAME="backup_correo_config_${TIMESTAMP}.tar.gz"

# Lista de ficheros y directorios a respaldar.
# Añade o quita elementos de esta lista según tus necesidades.
SOURCES_TO_BACKUP=(
    "/etc/postfix/"
    "/etc/dovecot/"
    "/etc/opendkim/"
    "/etc/aliases"
    "/etc/hosts"
    "/etc/mailname"
    "/etc/letsencrypt/"
    "/etc/ufw/"
)

# --- Comienzo del Script ---

echo "--- Iniciando el backup de configuración del servidor de correo ---"

# Expande la virgulilla a la ruta completa del directorio home
eval DEST_DIR="$DEST_DIR"

# 1. Crear el directorio de destino si no existe
echo "Verificando el directorio de destino: ${DEST_DIR}"
mkdir -p "${DEST_DIR}"
if [ $? -ne 0 ]; then
    echo "Error: No se pudo crear el directorio de destino. Saliendo."
    exit 1
fi

# 2. Crear un directorio temporal para reunir los ficheros
# Esto evita problemas de permisos y hace que el archivado sea más limpio.
TMP_DIR=$(mktemp -d)
echo "Directorio temporal creado en: ${TMP_DIR}"

# 3. Copiar todos los ficheros y directorios a la carpeta temporal
echo "Copiando ficheros de configuración..."
for item in "${SOURCES_TO_BACKUP[@]}"; do
    if [ -e "${item}" ]; then
        # La opción --parents preserva la estructura de directorios (ej: etc/postfix/)
        cp -r --parents "${item}" "${TMP_DIR}"
        echo "  -> Copiado: ${item}"
    else
        echo "  -> Aviso: No se encontró '${item}', se omitirá."
    fi
done

# Opcional: Copiar configuración de Fail2ban si existe
if [ -d "/etc/fail2ban" ]; then
    cp -r --parents "/etc/fail2ban" "${TMP_DIR}"
    echo "  -> Copiado: /etc/fail2ban (opcional)"
fi

# 4. Crear el archivo comprimido .tar.gz
echo "Creando el archivo comprimido..."
# La opción -C cambia al directorio temporal antes de comprimir.
# Esto elimina las rutas absolutas del archivo (ej: /tmp/tmp.XXXX/etc/...)
# y las deja como rutas relativas (ej: etc/...).
tar -czf "${DEST_DIR}/${ARCHIVE_NAME}" -C "${TMP_DIR}" .

if [ $? -ne 0 ]; then
    echo "Error: Falló la creación del archivo tar.gz. Saliendo."
    # Limpiar antes de salir
    rm -rf "${TMP_DIR}"
    exit 1
fi

# 5. Limpiar el directorio temporal
echo "Limpiando ficheros temporales..."
rm -rf "${TMP_DIR}"

# 6. Establecer permisos seguros para el backup (solo el propietario puede leer/escribir)
chmod 600 "${DEST_DIR}/${ARCHIVE_NAME}"

echo ""
echo "--- ✅ Backup completado con éxito ---"
echo "El archivo de respaldo se ha guardado en:"
echo "${DEST_DIR}/${ARCHIVE_NAME}"
echo "--------------------------------------"

exit 0
