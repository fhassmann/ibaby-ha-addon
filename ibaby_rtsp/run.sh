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

# Reinstalar (aunque sea la misma version ya horneada) pisa el fichero
# parcheado por patch_content_base.py -- reaplicar siempre tras esta seccion.
python3 /patch_content_base.py

bashio::log.info "Arrancando pyibaby.rtspd en el puerto ${RTSP_PORT}, path /${STREAM_NAME}"

# Apagado limpio: al parar el addon, Supervisor manda SIGTERM a este script.
# Sin reenviarla explicitamente al proceso Python hijo, el contenedor tarda
# de mas en pararse (hasta que Supervisor fuerza SIGKILL). CHILD_PID se
# actualiza en cada vuelta del bucle de reintento.
CHILD_PID=""
terminate() {
    bashio::log.info "Señal de parada recibida, cerrando pyibaby.rtspd..."
    if [ -n "${CHILD_PID}" ]; then
        kill -TERM "${CHILD_PID}" 2>/dev/null
        wait "${CHILD_PID}" 2>/dev/null
    fi
    exit 0
}
trap terminate TERM INT

# Bucle de reintento con backoff exponencial: si pyibaby.rtspd cae (camara
# offline, fallo de red, excepcion no controlada), se reinicia solo. El
# backoff (10s, 20s, 40s... tope 5min) evita machacar el login en la nube de
# iBaby si el fallo es persistente (credenciales mal, red caida) -- riesgo
# real de rate-limit/bloqueo de la cuenta con reintentos fijos cada 10s. Si
# una sesion aguanta al menos 60s antes de caer, se asume que funcionaba y el
# backoff se resetea al valor base. El Watchdog de HA (config.yaml) es la red
# de seguridad adicional si el proceso queda colgado sin llegar a salir.
RETRY_DELAY=10
MAX_RETRY_DELAY=300
while true; do
    start_ts=$(date +%s)
    python3 -m pyibaby.rtspd --port "${RTSP_PORT}" --path "/${STREAM_NAME}" &
    CHILD_PID=$!
    wait "${CHILD_PID}"
    exit_code=$?
    CHILD_PID=""
    uptime=$(( $(date +%s) - start_ts ))

    if [ "${uptime}" -ge 60 ]; then
        RETRY_DELAY=10
    fi

    bashio::log.warning "pyibaby.rtspd termino (codigo ${exit_code}, duro ${uptime}s). Reintentando en ${RETRY_DELAY}s..."
    sleep "${RETRY_DELAY}"

    RETRY_DELAY=$(( RETRY_DELAY * 2 ))
    if [ "${RETRY_DELAY}" -gt "${MAX_RETRY_DELAY}" ]; then
        RETRY_DELAY=${MAX_RETRY_DELAY}
    fi
done
