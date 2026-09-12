#!/usr/bin/with-contenv bashio

IBABY_EMAIL=$(bashio::config 'ibaby_email')
IBABY_PASSWORD=$(bashio::config 'ibaby_password')
RTSP_PORT=$(bashio::config 'rtsp_port')
STREAM_NAME=$(bashio::config 'stream_name')
PYIBABY_VERSION=$(bashio::config 'pyibaby_version')

export IBABY_EMAIL
export IBABY_PASSWORD

if [ -z "${IBABY_EMAIL}" ] || [ -z "${IBABY_PASSWORD}" ]; then
    bashio::log.fatal "Configura 'ibaby_email' e 'ibaby_password' en las opciones del addon."
    bashio::exit.nok
fi

# Si el usuario pide una version de pyibaby distinta a la horneada en la
# imagen, se reinstala en caliente (mantiene la version desacoplada de
# la imagen Docker, sin obligar a reconstruirla).
INSTALLED_VERSION=$(pip3 show pyibaby 2>/dev/null | awk '/^Version: /{print $2}')
if [ "${INSTALLED_VERSION}" != "${PYIBABY_VERSION}" ]; then
    bashio::log.info "Instalando pyibaby==${PYIBABY_VERSION} (version actual: ${INSTALLED_VERSION:-ninguna})..."
    if ! pip3 install --no-cache-dir --break-system-packages "pyibaby==${PYIBABY_VERSION}"; then
        bashio::log.fatal "No se pudo instalar pyibaby==${PYIBABY_VERSION}"
        bashio::exit.nok
    fi
fi

bashio::log.info "Arrancando pyibaby.rtspd en el puerto ${RTSP_PORT}, path /${STREAM_NAME}"

# Bucle de reintento: si pyibaby.rtspd cae (camara offline, fallo de red,
# excepcion no controlada), se reinicia solo. El Watchdog de HA (config.yaml)
# es la red de seguridad adicional si el propio proceso del addon muere.
while true; do
    python3 -m pyibaby.rtspd --port "${RTSP_PORT}" --path "/${STREAM_NAME}"
    exit_code=$?
    bashio::log.warning "pyibaby.rtspd termino (codigo ${exit_code}). Reintentando en 10s..."
    sleep 10
done
