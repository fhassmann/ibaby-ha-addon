#!/usr/bin/env python3
"""Corrige un bug de pyibaby.rtspd (validado contra 0.1.8): la cabecera
Content-Base de la respuesta DESCRIBE se construye sin puerto
(``rtsp://127.0.0.1{path}/``), lo que hace que un cliente RTSP que la tome de
forma literal (go2rtc, el motor interno que usa Home Assistant para
previsualizar camaras) intente el SETUP de cada pista contra el puerto RTSP
estandar (554) en vez del puerto real del addon. Consecuencia observada: HA
solo recupera la pista de audio del stream, nunca la de video.

Detalle completo (log de HA + analisis del bug) en
packages/doc/integraciones/aplicacion_camara_ibaby.md del repo de
configuracion de Home Assistant.

Idempotente: si ya esta parcheado, no hace nada. Si la libreria cambia de
version y esta linea ya no existe tal cual, avisa por stdout pero SIEMPRE
sale con codigo 0 -- no debe romper el arranque del addon por un problema
cosmetico de previsualizacion.
"""
import inspect
import sys

import pyibaby.rtspd as rtspd

OLD = 'headers={"Content-Base": f"rtsp://127.0.0.1{self.path}/"},'
NEW = 'headers={"Content-Base": f"rtsp://127.0.0.1:{self.sock.getsockname()[1]}{self.path}/"},'


def main() -> int:
    path = inspect.getfile(rtspd)
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()

    if NEW in src:
        print(f"[patch_content_base] {path}: ya parcheado, nada que hacer")
        return 0

    if OLD not in src:
        print(
            f"[patch_content_base] AVISO: no se encontro la linea esperada en "
            f"{path} -- la version de pyibaby instalada puede haber cambiado "
            f"este codigo. La previsualizacion en el dashboard de HA podria no "
            f"mostrar video (bug documentado); el resto del addon sigue "
            f"funcionando con normalidad."
        )
        return 0

    src = src.replace(OLD, NEW)
    with open(path, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"[patch_content_base] {path}: Content-Base corregido (puerto anadido)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
