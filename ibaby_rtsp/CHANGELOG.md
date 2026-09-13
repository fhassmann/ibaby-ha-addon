# Changelog

## 0.2.1

- MQTT desacoplado de la integración MQTT concreta de esta instalación:
  nuevas opciones `mqtt_host` / `mqtt_port` / `mqtt_username` /
  `mqtt_password` (todas opcionales). Si se rellenan, se usan tal cual; si
  se dejan vacías, sigue funcionando como en 0.2.0 (autodescubrimiento vía
  el servicio MQTT de Supervisor). Útil para compartir el addon
  públicamente o apuntarlo a un broker que no sea el gestionado por
  Supervisor.

## 0.2.0

- **Nuevo: sensores ambientales y PTZ vía MQTT.** La cámara empuja
  temperatura/humedad/CO2/VOC cada ~5s y soporta movimiento PTZ + modo
  privacidad, funciones que `pyibaby.rtspd` no expone. Nuevo proceso
  `control_bridge.py` (abre su propia sesión P2P, en paralelo a la de vídeo
  — el hardware soporta 2 sesiones concurrentes) que publica entidades en HA
  vía MQTT Discovery:
  - `sensor.ibaby_temperatura`, `sensor.ibaby_humedad`, `sensor.ibaby_co2`,
    `sensor.ibaby_voc`
  - `button.ibaby_ptz_arriba/abajo/izquierda/derecha`
  - `switch.ibaby_modo_privacidad` (con sincronización del estado real,
    también si se cambia desde la app oficial de iBaby)
- Nuevas opciones `sensors_enabled` / `ptz_enabled` (activadas por defecto,
  desactivables por separado).
- Requiere la integración MQTT en HA (`services: mqtt:want` — si no está
  disponible, el addon avisa por log y sigue sirviendo vídeo con
  normalidad, sin fallar el arranque).
- Reproductor de música y luz de proyector quedan fuera de esta versión
  (ver doc del repo de configuración de HA, sección de mejoras
  potenciales).

## 0.1.4

- Mejoras de log para depuración, motivadas por lo que costó diagnosticar el
  incidente de la 0.1.2→0.1.3:
  - Cada línea de `pyibaby.rtspd` (`[rtspd] ...`) lleva ahora hora
    (`HH:MM:SS`) delante, igual que las líneas de `bashio::log.*` — antes no
    la llevaba, y distinguir un log pegado reciente de uno de horas antes
    era ambiguo.
  - Línea única al arranque con la configuración efectiva (host, puerto,
    path, versión de `pyibaby`), sin credenciales.
- Recordatorio (sin cambio de código): los reinicios del propio contenedor
  forzados por Supervisor/Docker desde fuera (ej. el bug del watchdog de la
  0.1.2) **nunca aparecen en el log del addon** — solo en el log del
  Supervisor (`docker logs hassio_supervisor`, filtrando por `ibaby`).

## 0.1.3

- **Fix crítico**: el watchdog añadido en 0.1.2 provocaba un bucle de
  reinicio cada ~2-4 minutos. `pyibaby.rtspd` solo escuchaba en loopback
  (`--host 127.0.0.1` por defecto), y `[HOST]` en la sonda TCP del watchdog
  no resuelve a loopback en un addon `host_network` — la sonda fallaba
  siempre y Supervisor mataba/recreaba el addon en bucle (56 reinicios en
  ~4h en el despliegue real, con el consiguiente riesgo de rate-limit del
  login en la nube de iBaby). Corregido añadiendo `--host 0.0.0.0` al
  arranque de `pyibaby.rtspd` — ahora escucha en todas las interfaces, la
  sonda del watchdog llega. El `Content-Base` sigue fijo a `127.0.0.1` (bug
  de la librería, sección 6.2/6.4 de la doc), así que la URL de la
  integración *Generic Camera* en HA no cambia.
- **Si venías de la 0.1.2 con el watchdog dando problemas**: tras
  actualizar a esta versión, vuelve a activar el toggle "Watchdog" en la
  pestaña Info del addon (se desactiva solo, hay que reactivarlo a mano).

## 0.1.2

- Watchdog nativo de Supervisor (sondeo TCP sobre el puerto 8554): reinicia
  el addon si el proceso se queda colgado sin llegar a salir, caso que el
  bucle de reintento no cubre por sí solo.
- Backoff exponencial en el bucle de reintento (10s → 20s → 40s… tope 5min,
  se resetea si una sesión aguanta 60s o más) en vez de un reintento fijo
  cada 10s — evita machacar el login en la nube de iBaby si el fallo es
  persistente.
- Apagado limpio: se reenvía la señal de parada al proceso `pyibaby.rtspd`
  en vez de dejar que Supervisor tenga que forzar el cierre.
- Icono y logo propios para la ficha del addon.

## 0.1.1

- Fix: la cabecera `Content-Base` de `pyibaby.rtspd` iba sin puerto, lo que
  rompía la previsualización de vídeo en el dashboard de Home Assistant vía
  `go2rtc` (solo se recuperaba la pista de audio). Corregido con un parche
  aplicado sobre la instalación de la librería (`patch_content_base.py`).

## 0.1.0

- Primera versión: puente RTSP para cámaras iBaby M6S vía `pyibaby.rtspd`,
  con reintento automático, opciones desacopladas (credenciales, puerto,
  nombre del stream, versión de `pyibaby`).
