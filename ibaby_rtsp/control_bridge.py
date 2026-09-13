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

DEVICE_ID = "ibaby_m6s"
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
    "name": "iBaby M6S",
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
    lan = LANCamera(cam).connect()
    log(f"conectado a {cam.camid} ({cam.p2p_uid}) -- sesion de control/sensores")
    return lan


def publish_discovery(client: mqtt.Client) -> None:
    if SENSORS_ENABLED:
        sensors = [
            ("temperatura", "°C", "temperature"),
            ("humedad", "%", "humidity"),
            ("co2", "ppm", "carbon_dioxide"),
            ("voc", None, None),
        ]
        for key, unit, device_class in sensors:
            cfg = {
                "name": f"iBaby {key.capitalize()}",
                "unique_id": f"{DEVICE_ID}_{key}",
                "state_topic": f"{BASE_TOPIC}/sensor/{key}/state",
                "availability_topic": AVAILABILITY_TOPIC,
                "device": DEVICE_INFO,
            }
            if unit:
                cfg["unit_of_measurement"] = unit
            if device_class:
                cfg["device_class"] = device_class
                cfg["state_class"] = "measurement"
            client.publish(f"homeassistant/sensor/{DEVICE_ID}_{key}/config", json.dumps(cfg), retain=True)

    if PTZ_ENABLED:
        for key in PTZ_DIRECTIONS:
            cfg = {
                "name": f"iBaby PTZ {key}",
                "unique_id": f"{DEVICE_ID}_ptz_{key}",
                "command_topic": f"{BASE_TOPIC}/button/ptz_{key}/set",
                "availability_topic": AVAILABILITY_TOPIC,
                "device": DEVICE_INFO,
            }
            client.publish(f"homeassistant/button/{DEVICE_ID}_ptz_{key}/config", json.dumps(cfg), retain=True)

        cfg = {
            "name": "iBaby Modo privacidad",
            "unique_id": f"{DEVICE_ID}_privacy",
            "command_topic": f"{BASE_TOPIC}/switch/privacy/set",
            "state_topic": f"{BASE_TOPIC}/switch/privacy/state",
            "payload_on": "ON",
            "payload_off": "OFF",
            "availability_topic": AVAILABILITY_TOPIC,
            "device": DEVICE_INFO,
        }
        client.publish(f"homeassistant/switch/{DEVICE_ID}_privacy/config", json.dumps(cfg), retain=True)


def make_on_message(lan: LANCamera):
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

        if topic == f"{BASE_TOPIC}/switch/privacy/set":
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

    lan = connect_camera()

    client = mqtt.Client(client_id=f"{DEVICE_ID}_control_bridge")
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.will_set(AVAILABILITY_TOPIC, "offline", retain=True)
    client.on_message = make_on_message(lan)

    client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()

    client.publish(AVAILABILITY_TOPIC, "online", retain=True)
    publish_discovery(client)

    if PTZ_ENABLED:
        client.subscribe(f"{BASE_TOPIC}/button/+/set")
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

            if PTZ_ENABLED:
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
