ARG BUILD_FROM
FROM $BUILD_FROM

# Python 3 + pip (imagen base de HA es Alpine)
RUN apk add --no-cache python3 py3-pip

# Version por defecto "horneada" en la imagen para arranque rapido;
# run.sh reinstala en caliente si el usuario configura otra version
# distinta via la opcion pyibaby_version (sin reconstruir la imagen).
ARG PYIBABY_VERSION=0.1.8
RUN pip3 install --no-cache-dir --break-system-packages "pyibaby==${PYIBABY_VERSION}"

COPY run.sh /
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
