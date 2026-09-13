#!/usr/bin/env python3
"""Puente MQTT para funciones de la camara iBaby M6S que pyibaby.rtspd no
expone: sensores ambientales (temperatura/humedad/CO2/VOC) y PTZ + modo
privacidad. Publica entidades via MQTT Discovery de Home Assistant.

Abre su PROPIA sesion P2P con la camara (independiente de la de
pyibaby.rtspd) -- el hardware soporta 2 sesiones concurrentes como maximo
(documentado en pyibaby.rtspd), asi que este proceso y el de video ocupan
una cada uno. No anadir un tercer proceso con sesion propia sin revisar
esto primero.

Reproductor de musica y luz de proyector quedan fuera de alcance por ahora
(ver packages/doc/integraciones/aplicacion_camara_ibaby.md, seccion de
mejoras potenciales, en el repo de configuracion de HA).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time

import paho.mqtt.client as mqtt

from pyibaby import IBabyCloud, LANCamera
from pyibaby.protocol import PTZ_UP, PTZ_DOWN, PTZ_LEFT, PTZ_RIGHT, PTZ_STOP

EMAIL = os.environ["IBABY_EMAIL"]
PASSWORD = os.environ["IBABY_PASSWORD"]
SENSORS_ENABLED = os.environ.get("SENSORS_ENABLED", "true") == "true"
PTZ_ENABLED = os.environ.get("PTZ_ENABLED", "true") == "true"

MQTT_HOST = os.environ["MQTT_HOST"]
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_USERNAME = os.environ.get("MQTT_USERNAME") or None
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD") or None

# Mismo nombre que la opcion stream_name (el path RTSP, ej. "ibaby") para que
# topics MQTT y unique_id de las entidades queden bajo un unico nombre
# configurable, coherente con el resto del addon -- no un identificador fijo
# aparte. Saneado a lo que MQTT/HA aceptan en un topic/unique_id.
_stream_name = os.environ.get("STREAM_NAME", "ibaby").strip() or "ibaby"
DEVICE_ID = re.sub(r"[^a-zA-Z0-9_-]", "_", _stream_name).lower()
BASE_TOPIC = f"ibaby_rtsp/{DEVICE_ID}"
AVAILABILITY_TOPIC = f"{BASE_TOPIC}/status"

PTZ_DIRECTIONS = {
    "arriba": PTZ_UP,
    "abajo": PTZ_DOWN,
    "izquierda": PTZ_LEFT,
    "derecha": PTZ_RIGHT,
}
PTZ_NUDGE_S = 0.4  # duracion del movimiento por pulsacion antes de mandar STOP

DEVICE_INFO = {
    "identifiers": [DEVICE_ID],
    "name": f"iBaby M6S ({_stream_name})",
    "manufacturer": "iBaby",
    "model": "M6S",
}


def log(*a) -> None:
    print("[control_bridge]", *a, flush=True)


def connect_camera() -> LANCamera:
    cloud = IBabyCloud()
    cameras = cloud.login(EMAIL, PASSWORD)
    cam = next((c for c in cameras if c.is_pppp), None)
    if cam is None:
        raise RuntimeError("No se encontro ninguna camara PPPP en la cuenta")

    # El handshake P2P tiene un timeout corto (5s en la libreria) y puede
    # chocar con la sesion de pyibaby.rtspd si ambas piden conectar casi a
    # la vez al arrancar el addon. Unos reintentos rapidos aqui evitan tener
    # que reiniciar el proceso entero (y repetir el login en la nube) por
    # una contencion pasajera de unos segundos.
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            lan = LANCamera(cam).connect()
            log(f"conectado a {cam.camid} ({cam.p2p_uid}) -- sesion de control/sensores")
            return lan
        except TimeoutError as e:
            last_error = e
            log(f"handshake P2P fallo (intento {attempt}/3): {e!r} -- reintentando en 5s")
            time.sleep(5)
    raise last_error or RuntimeError("no se pudo conectar tras 3 intentos")


def probe_privacy_support(lan: LANCamera) -> bool:
    """El subsistema de proyector/privacidad (GET_PROJECTORLAMP, cmd 5383)
    no esta soportado por todas las camaras -- confirmado en real
    2026-09-13: en una M6S, el comando de modo privacidad se envia sin
    error pero no tiene ningun efecto fisico, y esta consulta nunca
    responde. En vez de asumir por modelo (camtype no documenta de forma
    fiable que funciones trae cada uno), se comprueba la capacidad real del
    dispositivo al conectar: un par de intentos sin respuesta y se da por
    no soportado, para no publicar una entidad condenada a quedarse en
    'unknown' para siempre."""
    for _ in range(2):
        if lan.get_projector(timeout=4.0) is not None:
            return True
    return False


def _base_cfg(domain: str, object_id: str, name: str) -> dict:
    """Campos comunes a toda entidad MQTT Discovery de este addon.

    has_entity_name=True: el nombre visible final lo compone HA como
    "<nombre del device> <name>" (ej. "iBaby M6S (ibaby) Temperatura"), en
    vez de tener que repetir "iBaby" a mano en cada entidad.

    default_entity_id (NO "object_id" -- probado en real: "object_id" en el
    payload de discovery no influye en el entity_id resultante, solo en el
    topic de discovery; el campo que si lo fija es default_entity_id, con el
    dominio incluido) fija el entity_id de forma deterministica (ej.
    sensor.<stream_name>_temperatura) -- sin esto, HA lo deriva del "name" +
    nombre del device combinados y da algo largo y redundante
    (sensor.ibaby_m6s_ibaby_temperatura). Solo aplica la PRIMERA vez que se
    crea la entidad (mismo unique_id) -- un cambio posterior no renombra una
    entidad ya existente, hay que borrarla a mano para que se recree.
    """
    return {
        "name": name,
        "has_entity_name": True,
        "unique_id": object_id,
        "default_entity_id": f"{domain}.{object_id}",
        "availability_topic": AVAILABILITY_TOPIC,
        "device": DEVICE_INFO,
    }


def publish_discovery(client: mqtt.Client, privacy_supported: bool) -> None:
    if SENSORS_ENABLED:
        sensors = [
            ("temperatura", "Temperatura", "°C", "temperature"),
            ("humedad", "Humedad", "%", "humidity"),
            ("co2", "CO2", "ppm", "carbon_dioxide"),
            ("voc", "VOC", None, None),
        ]
        for key, name, unit, device_class in sensors:
            object_id = f"{DEVICE_ID}_{key}"
            cfg = _base_cfg("sensor", object_id, name)
            cfg["state_topic"] = f"{BASE_TOPIC}/sensor/{key}/state"
            if unit:
                cfg["unit_of_measurement"] = unit
            if device_class:
                cfg["device_class"] = device_class
                cfg["state_class"] = "measurement"
            client.publish(f"homeassistant/sensor/{object_id}/config", json.dumps(cfg), retain=True)

    if PTZ_ENABLED:
        for key, label in [("arriba", "Arriba"), ("abajo", "Abajo"), ("izquierda", "Izquierda"), ("derecha", "Derecha")]:
            object_id = f"{DEVICE_ID}_ptz_{key}"
            cfg = _base_cfg("button", object_id, f"PTZ {label}")
            cfg["command_topic"] = f"{BASE_TOPIC}/button/ptz_{key}/set"
            client.publish(f"homeassistant/button/{object_id}/config", json.dumps(cfg), retain=True)

        if privacy_supported:
            object_id = f"{DEVICE_ID}_privacy"
            cfg = _base_cfg("switch", object_id, "Modo privacidad")
            cfg["command_topic"] = f"{BASE_TOPIC}/switch/privacy/set"
            cfg["state_topic"] = f"{BASE_TOPIC}/switch/privacy/state"
            cfg["payload_on"] = "ON"
            cfg["payload_off"] = "OFF"
            client.publish(f"homeassistant/switch/{object_id}/config", json.dumps(cfg), retain=True)


def make_on_message(lan: LANCamera, privacy_supported: bool):
    def on_message(_client, _userdata, msg: mqtt.MQTTMessage) -> None:
        topic = msg.topic
        payload = msg.payload.decode(errors="replace").strip()

        for key, direction in PTZ_DIRECTIONS.items():
            if topic == f"{BASE_TOPIC}/button/ptz_{key}/set":
                log(f"PTZ {key}")
                try:
                    lan.ptz(direction)
                    time.sleep(PTZ_NUDGE_S)
                    lan.ptz(PTZ_STOP)
                except Exception as e:  # no tirar el proceso por un comando suelto
                    log(f"AVISO: fallo enviando PTZ {key}: {e!r}")
                return

        if topic == f"{BASE_TOPIC}/switch/privacy/set" and privacy_supported:
            on = payload.upper() == "ON"
            log(f"modo privacidad -> {'ON' if on else 'OFF'}")
            try:
                lan.privacy_mode(on)
            except Exception as e:
                log(f"AVISO: fallo enviando modo privacidad: {e!r}")

    return on_message


def main() -> int:
    if not SENSORS_ENABLED and not PTZ_ENABLED:
        log("sensores y PTZ desactivados por opciones -- nada que hacer, saliendo")
        return 0

    try:
        lan = connect_camera()
    except Exception as e:
        log(f"no se pudo conectar con la camara ({e}) -- revisa ibaby_email/ibaby_password en la configuracion del addon")
        return 1

    privacy_supported = False
    if PTZ_ENABLED:
        privacy_supported = probe_privacy_support(lan)
        log(f"modo privacidad: {'soportado' if privacy_supported else 'NO soportado por esta camara -- switch no publicado'}")

    # callback_api_version explicito (paho-mqtt >= 2.0): sin esto, paho usa
    # VERSION1 por defecto con un DeprecationWarning en cada arranque. VERSION2
    # cambia la firma de on_connect/on_disconnect/on_publish/on_subscribe (anaden
    # reason_code/properties), pero este addon solo registra on_message, cuya
    # firma (client, userdata, message) no cambia entre versiones -- migracion
    # segura sin tocar make_on_message.
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{DEVICE_ID}_control_bridge")
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)
    client.on_message = make_on_message(lan, privacy_supported)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()

    client.publish(AVAILABILITY_TOPIC, "online", retain=True)
    publish_discovery(client, privacy_supported)

    if PTZ_ENABLED:
        client.subscribe(f"{BASE_TOPIC}/button/+/set")
        if privacy_supported:
            client.subscribe(f"{BASE_TOPIC}/switch/privacy/set")

    log(f"listo (sensores={'on' if SENSORS_ENABLED else 'off'}, ptz={'on' if PTZ_ENABLED else 'off'})")

    try:
        while True:
            if SENSORS_ENABLED:
                reading = lan.read_sensors(timeout=15.0)
                if reading is not None:
                    if reading.temperature_c is not None:
                        client.publish(f"{BASE_TOPIC}/sensor/temperatura/state", f"{reading.temperature_c:.1f}")
                    if reading.humidity_pct is not None:
                        client.publish(f"{BASE_TOPIC}/sensor/humedad/state", f"{reading.humidity_pct:.1f}")
                    if reading.co2_ppm is not None:
                        client.publish(f"{BASE_TOPIC}/sensor/co2/state", str(reading.co2_ppm))
                    if reading.voc is not None:
                        client.publish(f"{BASE_TOPIC}/sensor/voc/state", str(reading.voc))
            else:
                time.sleep(15.0)

            if PTZ_ENABLED and privacy_supported:
                # Sincroniza el estado real del switch (por si se cambio desde
                # la app oficial de iBaby, no solo desde HA).
                proj = lan.get_projector(timeout=4.0)
                if proj is not None:
                    client.publish(
                        f"{BASE_TOPIC}/switch/privacy/state",
                        "ON" if proj.privacy else "OFF",
                    )
    finally:
        client.publish(AVAILABILITY_TOPIC, "offline", retain=True)
        client.loop_stop()
        lan.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
