# O mysqlclient (driver do MySQL recomendado pelo Django) é compilado num estágio à parte,
# para a imagem final levar só a biblioteca cliente, sem compilador.
FROM python:3.13-slim AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libmariadb3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=build /wheels /wheels
RUN pip install --no-index /wheels/*.whl && rm -rf /wheels && useradd --create-home --uid 10001 argo
COPY manage.py .
COPY argo ./argo

USER argo
EXPOSE 8000
# ARGO_SERVICE escolhe o serviço: identity, catalog ou orders (o worker usa o comando do Celery)
ENV DJANGO_SETTINGS_MODULE=argo.settings
CMD ["python", "manage.py", "serve"]
