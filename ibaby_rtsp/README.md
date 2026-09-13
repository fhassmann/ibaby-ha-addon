# iBaby RTSP Bridge

Puente RTSP en Python puro para cámaras iBaby M6S (y compatibles con el mismo
protocolo P2P/PPPP de ThroughTek), basado en la librería no oficial
[`pyibaby`](https://pypi.org/project/pyibaby/).

## Cómo funciona

El addon corre `python -m pyibaby.rtspd`, que:

1. Inicia sesión en la nube de iBaby con tu email/contraseña.
2. Descubre la cámara en tu red local (LAN) vía el protocolo PPPP.
3. Sirve el vídeo (H.264) y audio (G.711) de la cámara como una fuente RTSP
   estándar en `rtsp://IP_DE_HOME_ASSISTANT:<rtsp_port>/<stream_name>`.

No requiere la app oficial de iBaby ni depende de sus servidores para el
streaming (solo para el login inicial).

## Opciones

| Opción | Descripción | Por defecto |
|---|---|---|
| `ibaby_email` | Email de tu cuenta iBaby | — |
| `ibaby_password` | Contraseña de tu cuenta iBaby | — |
| `rtsp_port` | Puerto RTSP a exponer | `8554` |
| `stream_name` | Nombre del path RTSP (`/nombre`) | `ibaby` |
| `pyibaby_version` | Versión de `pyibaby` a usar (PyPI) | `0.1.8` |
| `sensors_enabled` | Publica temperatura/humedad/CO2/VOC por MQTT | `true` |
| `ptz_enabled` | Publica botones PTZ y el switch de privacidad por MQTT | `true` |

`sensors_enabled`/`ptz_enabled` necesitan la integración **MQTT** en Home
Assistant. Si no está disponible, el addon avisa por log y sigue sirviendo
vídeo con normalidad — no falla el arranque.

## Sensores y PTZ (opcional, vía MQTT)

Si `sensors_enabled`/`ptz_enabled` están activos y hay MQTT configurado en HA,
aparecen automáticamente (MQTT Discovery, sin configuración adicional):

- `sensor.ibaby_temperatura`, `sensor.ibaby_humedad`, `sensor.ibaby_co2`,
  `sensor.ibaby_voc` — telemetría que la propia cámara empuja cada ~5s.
- `button.ibaby_ptz_arriba/abajo/izquierda/derecha` — movimiento PTZ.
- `switch.ibaby_modo_privacidad` — apunta la cámara hacia abajo / la
  restaura; el estado se sincroniza también si se cambia desde la app
  oficial de iBaby.

## Añadir la cámara en Home Assistant

Settings → Devices & Services → Add Integration → **Generic Camera**, con la
URL de streaming:

```
rtsp://IP_DE_HOME_ASSISTANT:8554/ibaby
```

## Seguridad

El puerto RTSP corre en modo *host networking* y **no debe exponerse** al
router/Internet: solo debe ser accesible desde tu red local.

## Aviso

`pyibaby` es un proyecto de ingeniería inversa no oficial, sin relación con
iBaby Labs ni ThroughTek. Úsalo bajo tu propia responsabilidad.
