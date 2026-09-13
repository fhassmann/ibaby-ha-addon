#!/usr/bin/with-contenv bashio

IBABY_EMAIL=$(bashio::config 'ibaby_email')
IBABY_PASSWORD=$(bashio::config 'ibaby_password')
RTSP_PORT=$(bashio::config 'rtsp_port')
STREAM_NAME=$(bashio::config 'stream_name')
PYIBABY_VERSION=$(bashio::config 'pyibaby_version')
SENSORS_ENABLED=$(bashio::config 'sensors_enabled')
PTZ_ENABLED=$(bashio::config 'ptz_enabled')
MQTT_HOST_OPT=$(bashio::config 'mqtt_host')
MQTT_PORT_OPT=$(bashio::config 'mqtt_port')
MQTT_USERNAME_OPT=$(bashio::config 'mqtt_username')
MQTT_PASSWORD_OPT=$(bashio::config 'mqtt_password')

export IBABY_EMAIL
export IBABY_PASSWORD
export SENSORS_ENABLED
export PTZ_ENABLED

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

bashio::log.info "Config: host=0.0.0.0 puerto=${RTSP_PORT} path=/${STREAM_NAME} pyibaby=${PYIBABY_VERSION} sensores=${SENSORS_ENABLED} ptz=${PTZ_ENABLED}"

# Sensores/PTZ necesitan un broker MQTT para publicar entidades en HA.
# Prioridad: 1) mqtt_host configurado a mano en las opciones (desacopla el
# addon de la integracion MQTT concreta de esta instalacion -- necesario
# para compartirlo publicamente o apuntar a otro broker); 2) si se deja
# vacio, autodescubrimiento via el servicio MQTT de Supervisor (services:
# mqtt:want en config.yaml). Si no hay ninguna de las dos, sensores/PTZ se
# desactivan con un aviso -- el video no se ve afectado, no bloquea el
# arranque.
if [ "${SENSORS_ENABLED}" = "true" ] || [ "${PTZ_ENABLED}" = "true" ]; then
    if [ -n "${MQTT_HOST_OPT}" ]; then
        bashio::log.info "MQTT: usando configuracion manual (mqtt_host=${MQTT_HOST_OPT})."
        export MQTT_HOST="${MQTT_HOST_OPT}"
        export MQTT_PORT="${MQTT_PORT_OPT:-1883}"
        export MQTT_USERNAME="${MQTT_USERNAME_OPT}"
        export MQTT_PASSWORD="${MQTT_PASSWORD_OPT}"
        BRIDGE_ENABLED=true
    elif bashio::services.available 'mqtt'; then
        bashio::log.info "MQTT: autodetectado via el servicio de Supervisor."
        export MQTT_HOST=$(bashio::services 'mqtt' 'host')
        export MQTT_PORT=$(bashio::services 'mqtt' 'port')
        export MQTT_USERNAME=$(bashio::services 'mqtt' 'username')
        export MQTT_PASSWORD=$(bashio::services 'mqtt' 'password')
        BRIDGE_ENABLED=true
    else
        bashio::log.warning "MQTT no configurado (ni mqtt_host ni servicio de Supervisor) -- sensores/PTZ desactivados (video no se ve afectado)."
        BRIDGE_ENABLED=false
    fi
else
    BRIDGE_ENABLED=false
fi

export PYTHONUNBUFFERED=1

# Apagado limpio: al parar el addon, Supervisor manda SIGTERM a este script.
# Sin reenviarla explicitamente a los procesos Python hijos, el contenedor
# tarda de mas en pararse (hasta que Supervisor fuerza SIGKILL). Los PID de
# los hijos activos se guardan en ficheros porque las dos funciones de bucle
# de abajo corren en subshells (backgrounded) -- una variable de shell escrita
# ahi no es visible aqui, un fichero si.
RTSPD_PIDFILE=/tmp/rtspd_child.pid
BRIDGE_PIDFILE=/tmp/bridge_child.pid
terminate() {
    bashio::log.info "Señal de parada recibida, cerrando procesos..."
    for f in "${RTSPD_PIDFILE}" "${BRIDGE_PIDFILE}"; do
        if [ -f "${f}" ]; then
            pid=$(cat "${f}" 2>/dev/null)
            [ -n "${pid}" ] && kill -TERM "${pid}" 2>/dev/null
        fi
    done
    sleep 1
    exit 0
}
trap terminate TERM INT

# Bucle de reintento con backoff exponencial (10s, 20s, 40s... tope 5min,
# reseteado a 10s si una sesion aguanta 60s o mas) -- evita machacar el login
# en la nube de iBaby si el fallo es persistente (credenciales mal, red
# caida, MQTT caido). Mismo patron para el video (pyibaby.rtspd) y el puente
# de sensores/PTZ (control_bridge.py), cada uno en su propia funcion para
# poder correr en paralelo. pyibaby.rtspd no antepone hora a sus propias
# lineas ([rtspd] connected to...) a diferencia de bashio::log.* -- costo
# confusion real diagnosticando un incidente pasado, de ahi la sustitucion de
# proceso que le antepone hora a cada linea en las dos funciones.

rtspd_loop() {
    local retry_delay=10
    local max_retry_delay=300
    while true; do
        local start_ts=$(date +%s)
        python3 -u -m pyibaby.rtspd --host 0.0.0.0 --port "${RTSP_PORT}" --path "/${STREAM_NAME}" \
            > >(while IFS= read -r line; do echo "$(date '+%H:%M:%S') ${line}"; done) 2>&1 &
        echo $! > "${RTSPD_PIDFILE}"
        wait "$(cat "${RTSPD_PIDFILE}")"
        local exit_code=$?
        rm -f "${RTSPD_PIDFILE}"
        local uptime=$(( $(date +%s) - start_ts ))

        [ "${uptime}" -ge 60 ] && retry_delay=10

        bashio::log.warning "pyibaby.rtspd termino (codigo ${exit_code}, duro ${uptime}s). Reintentando en ${retry_delay}s..."
        sleep "${retry_delay}"

        retry_delay=$(( retry_delay * 2 ))
        [ "${retry_delay}" -gt "${max_retry_delay}" ] && retry_delay=${max_retry_delay}
    done
}

bridge_loop() {
    local retry_delay=10
    local max_retry_delay=300
    while true; do
        local start_ts=$(date +%s)
        python3 -u /control_bridge.py \
            > >(while IFS= read -r line; do echo "$(date '+%H:%M:%S') ${line}"; done) 2>&1 &
        echo $! > "${BRIDGE_PIDFILE}"
        wait "$(cat "${BRIDGE_PIDFILE}")"
        local exit_code=$?
        rm -f "${BRIDGE_PIDFILE}"
        local uptime=$(( $(date +%s) - start_ts ))

        [ "${uptime}" -ge 60 ] && retry_delay=10

        bashio::log.warning "control_bridge.py termino (codigo ${exit_code}, duro ${uptime}s). Reintentando en ${retry_delay}s..."
        sleep "${retry_delay}"

        retry_delay=$(( retry_delay * 2 ))
        [ "${retry_delay}" -gt "${max_retry_delay}" ] && retry_delay=${max_retry_delay}
    done
}

rtspd_loop &

if [ "${BRIDGE_ENABLED}" = "true" ]; then
    bridge_loop &
fi

wait
