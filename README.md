# ibaby-ha-addon

Repositorio de Apps (add-ons) de Home Assistant, desarrollado originalmente
para uso propio y compartido públicamente por si le sirve a alguien más.

## Estado del proyecto

**Compartido, no mantenido activamente.** Esto lo mantengo en mi tiempo libre
para mi propio uso — funciona bien para mi instalación (una cámara iBaby M6S
concreta), pero no puedo comprometerme a dar soporte, revisar Issues/PRs en
un plazo determinado, ni probarlo contra hardware/modelos distintos al mío.
Se comparte tal cual (licencia MIT, ver [`LICENSE`](LICENSE)), bajo tu propio
riesgo. Si te sirve, genial; si algo falla y te animas a mandar un PR con el
fix, bienvenido sea, pero no esperes una respuesta rápida.

## Apps disponibles

- [`ibaby_rtsp`](ibaby_rtsp/) — puente RTSP en Python puro para cámaras iBaby M6S, basado en [`pyibaby`](https://pypi.org/project/pyibaby/).

## Instalación en Home Assistant

1. Settings → Apps → Repositories.
2. Añadir: `https://github.com/fhassmann/ibaby-ha-addon`
3. Instalar "iBaby RTSP Bridge" desde el catálogo de Apps.

## Aviso

Add-ons no oficiales, sin relación ni afiliación con iBaby Labs ni ThroughTek.
`pyibaby` (la librería en la que se apoya `ibaby_rtsp`) es una implementación
de ingeniería inversa no oficial del protocolo P2P/PPPP de ThroughTek.
Probado únicamente contra una iBaby M6S concreta — algunas funciones (modo
privacidad, sensores de CO2/VOC) no están soportadas en ese modelo/firmware
y podrían funcionar distinto, o no funcionar, en otro.
