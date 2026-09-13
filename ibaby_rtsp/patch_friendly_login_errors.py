#!/usr/bin/env python3
"""Convierte un fallo al conectar con la camara (login de nube invalido,
credenciales mal formadas, sin respuesta P2P, etc.) en un aviso de una linea
por el log del addon, en vez del traceback de Python completo que da
``pyibaby.rtspd`` por su cuenta.

Motivado por un incidente real (2026-09-13): ``ibaby_email``/
``ibaby_password`` quedaron mal en la configuracion del addon (ver
packages/doc/integraciones/aplicacion_camara_ibaby.md, nota operativa de la
seccion 4) y el log solo mostraba un traceback de
``pyibaby.cloud.CloudError`` dificil de interpretar a simple vista para
alguien sin contexto de Python.

Se aplica DESPUES de ``patch_stream_quality.py`` -- el bloque que busca
incluye ya el flag ``--quality`` que anade ese patch.

Idempotente: si ya esta parcheado, no hace nada. Si la libreria cambia de
version y este bloque ya no existe tal cual, avisa por stdout pero SIEMPRE
sale con codigo 0 -- no debe romper el arranque del addon; en el peor caso
se pierde el mensaje bonito y vuelve el traceback crudo, no un addon roto.
"""
import inspect
import sys

import pyibaby.rtspd as rtspd

OLD = '''    args = ap.parse_args()

    cam = resolve_camera(args.camid)
    lan = LANCamera(cam)
    lan.connect()
    _log(f"connected to {cam.camid} ({cam.p2p_uid})")
    if args.quality:
        lan.set_quality(args.quality)
        _log(f"stream quality set to {args.quality}")
    source = CameraSource(lan, audio=not args.no_audio)'''

NEW = '''    args = ap.parse_args()

    try:
        cam = resolve_camera(args.camid)
        lan = LANCamera(cam)
        lan.connect()
    except Exception as e:
        _log(f"no se pudo conectar con la camara ({e}) -- revisa ibaby_email/ibaby_password en la configuracion del addon")
        return 1
    _log(f"connected to {cam.camid} ({cam.p2p_uid})")
    if args.quality:
        lan.set_quality(args.quality)
        _log(f"stream quality set to {args.quality}")
    source = CameraSource(lan, audio=not args.no_audio)'''


def main() -> int:
    path = inspect.getfile(rtspd)
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    if NEW in src:
        print(f"[patch_friendly_login_errors] {path}: ya parcheado, nada que hacer")
        return 0

    if OLD not in src:
        print(
            f"[patch_friendly_login_errors] AVISO: no se encontro el bloque esperado en "
            f"{path} -- la version de pyibaby instalada, o el orden de los patches, puede "
            f"haber cambiado. Un fallo de login volvera a mostrar el traceback de Python "
            f"crudo en el log; el resto del addon sigue funcionando con normalidad."
        )
        return 0

    src = src.replace(OLD, NEW)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"[patch_friendly_login_errors] {path}: errores de login/conexion ahora dan un aviso claro, sin traceback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
