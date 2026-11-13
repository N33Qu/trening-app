# syntax=docker/dockerfile:1

ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install --only-binary=:all: -r requirements.txt \
 && /opt/venv/bin/pip uninstall -y pip \
 && find /opt/venv -type d -name "__pycache__" -prune -exec rm -rf {} +

FROM ${PYTHON_IMAGE} AS runtime
ARG APP_VERSION=dev
LABEL org.opencontainers.image.title="trening-app" \
      org.opencontainers.image.description="Trening – planowanie i monitorowanie treningu siłowego" \
      org.opencontainers.image.source="https://github.com/N33Qu/trening-app" \
      org.opencontainers.image.version="${APP_VERSION}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:${PATH}" \
    APP_ENV=production \
    APP_VERSION=${APP_VERSION} \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prom \
    GUNICORN_WORKERS=2

RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && { pip uninstall -y pip setuptools wheel 2>/dev/null || true; } \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY wsgi.py gunicorn.conf.py ./
COPY app ./app
RUN pybabel compile -d app/translations \
 && chmod -R u=rwX,go=rX /app

USER 10001:10001
EXPOSE 8000
CMD ["gunicorn", "-c", "gunicorn.conf.py", "wsgi:app"]
