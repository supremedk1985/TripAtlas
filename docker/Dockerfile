# TripAtlas — one image: the API (Python) serves the web UI (static build).
# Build from the repository root:  docker build -f docker/Dockerfile -t tripatlas .

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TRIPATLAS_DATA_DIR=/data \
    TRIPATLAS_WEB_DIR=/app/web
WORKDIR /app
COPY server/pyproject.toml ./server/
COPY server/tripatlas ./server/tripatlas
RUN pip install --no-cache-dir ./server && rm -rf ./server
COPY --from=web /web/build /app/web
RUN groupadd --gid 1000 tripatlas && useradd --system --uid 1000 --gid 1000 --home /data tripatlas \
    && mkdir -p /data && chown tripatlas:tripatlas /data
USER tripatlas
VOLUME /data
EXPOSE 8097
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8097/api/health', timeout=4)"
# --proxy-headers: behind a reverse proxy (Caddy, Traefik, nginx) the client address and scheme are taken from it.
CMD ["uvicorn", "tripatlas.main:app", "--host", "0.0.0.0", "--port", "8097", "--proxy-headers", "--forwarded-allow-ips", "*"]
