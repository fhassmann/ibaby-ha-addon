ARG BUILD_FROM
FROM $BUILD_FROM

# Python 3 + pip (imagen base de HA es Alpine)
RUN apk add --no-cache python3 py3-pip

# Version por defecto "horneada" en la imagen para arranque rapido;
# run.sh reinstala en caliente si el usuario configura otra version
# distinta via la opcion pyibaby_version (sin reconstruir la imagen).
ARG PYIBABY_VERSION=0.1.8
RUN pip3 install --no-cache-dir --break-system-packages "pyibaby==${PYIBABY_VERSION}" paho-mqtt

# Fix de un bug de pyibaby (Content-Base sin puerto en el DESCRIBE RTSP, ver
# patch_content_base.py), flag --quality anadido a rtspd.py (ver
# patch_stream_quality.py) y errores de login/conexion legibles en vez de
# traceback crudo (ver patch_friendly_login_errors.py, aplicado el ultimo
# porque su bloque a buscar incluye ya el --quality del patch anterior) --
# los tres se reaplican tambien en run.sh tras cualquier reinstalacion en
# caliente por la opcion pyibaby_version.
COPY patch_content_base.py /
COPY patch_stream_quality.py /
COPY patch_friendly_login_errors.py /
RUN python3 /patch_content_base.py && python3 /patch_stream_quality.py && python3 /patch_friendly_login_errors.py

COPY control_bridge.py /
COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
