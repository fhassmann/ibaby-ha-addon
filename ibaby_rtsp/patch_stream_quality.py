#!/usr/bin/env python3
"""Anade un flag ``--quality`` a ``pyibaby.rtspd`` (validado contra 0.1.8), que
no lo expone por su cuenta pese a que la libreria si soporta pedirle a la
camara un perfil de resolucion/bitrate mas bajo (comando nativo
``IBABY_SET_STREAMCFG``, cmd 273, via ``LANCamera.set_quality()`` en
``client.py``). Pensado para conexiones remotas/con poco ancho de banda,
donde el stream a resolucion completa produce cortes ("paron") en el video.

El cambio de calidad es GLOBAL en el encoder de la camara (afecta a
cualquier visor, no solo a esta sesion) y tarda hasta el siguiente keyframe
en aplicarse -- se pide una vez, justo tras conectar y antes de arrancar el
fanout de frames, no en cada frame.

Detalle completo en packages/doc/integraciones/aplicacion_camara_ibaby.md
del repo de configuracion de Home Assistant.

Idempotente: si ya esta parcheado, no hace nada. Si la libreria cambia de
version y este bloque ya no existe tal cual, avisa por stdout pero SIEMPRE
sale con codigo 0 -- no debe romper el arranque del addon por no poder
ajustar la calidad (el video sigue funcionando a la resolucion que ya
tuviera la camara).
"""
import inspect
import sys

import pyibaby.rtspd as rtspd

OLD = '''    ap.add_argument("--no-talk", action="store_true", help="disable the talk-back (RTSP backchannel)")
    args = ap.parse_args()

    cam = resolve_camera(args.camid)
    lan = LANCamera(cam)
    lan.connect()
    _log(f"connected to {cam.camid} ({cam.p2p_uid})")
    source = CameraSource(lan, audio=not args.no_audio)'''

NEW = '''    ap.add_argument("--no-talk", action="store_true", help="disable the talk-back (RTSP backchannel)")
    ap.add_argument(
        "--quality",
        default=None,
        help="live-stream preset from pyibaby.protocol.STREAM_PRESETS (1080p, 720p, 720p_eco, 360p, tiny)",
    )
    args = ap.parse_args()

    cam = resolve_camera(args.camid)
    lan = LANCamera(cam)
    lan.connect()
    _log(f"connected to {cam.camid} ({cam.p2p_uid})")
    if args.quality:
        lan.set_quality(args.quality)
        _log(f"stream quality set to {args.quality}")
    source = CameraSource(lan, audio=not args.no_audio)'''

# Marcador de idempotencia MAS ESPECIFICO que el bloque NEW completo: un
# patch posterior (patch_friendly_login_errors.py) reescribe el entorno de
# ese bloque (envuelve resolve_camera/connect en un try/except), asi que
# "NEW in src" deja de ser cierto en cuanto ese otro patch se aplica --
# aunque el flag --quality siga funcionando perfectamente. Comprobar solo
# esta linea (que ningun otro patch toca) evita un falso "AVISO: no
# parcheado" en cada arranque normal del addon a partir de ahi.
QUALITY_FLAG_MARKER = 'help="live-stream preset from pyibaby.protocol.STREAM_PRESETS (1080p, 720p, 720p_eco, 360p, tiny)",'


def main() -> int:
    path = inspect.getfile(rtspd)
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    if QUALITY_FLAG_MARKER in src:
        print(f"[patch_stream_quality] {path}: ya parcheado, nada que hacer")
        return 0

    if OLD not in src:
        print(
            f"[patch_stream_quality] AVISO: no se encontro el bloque esperado en "
            f"{path} -- la version de pyibaby instalada puede haber cambiado "
            f"este codigo. La opcion 'stream_quality' del addon no tendra efecto "
            f"(la camara seguira en su resolucion actual); el resto del addon "
            f"sigue funcionando con normalidad."
        )
        return 0

    src = src.replace(OLD, NEW)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"[patch_stream_quality] {path}: flag --quality anadido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
