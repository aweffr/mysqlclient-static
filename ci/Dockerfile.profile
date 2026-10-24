ARG BASE
FROM ${BASE}
ARG DJANGO
ARG TOOLS
RUN python -m pip install --no-cache-dir --only-binary=:all: "Django==${DJANGO}" ${TOOLS} \
    && python -m pip check \
    && python -c "import MySQLdb, django; print(MySQLdb.version_info, django.get_version())"
