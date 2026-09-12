# Changelog

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
