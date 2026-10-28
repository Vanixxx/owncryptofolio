# Two stages: Node builds the frontend, Python serves API and frontend (ADR 0016).
# Node is not part of the runtime image.
# Build from the repository root, so the licence files get into the image:
#   docker build -f src/Dockerfile -t owncryptofolio .
# (the root .dockerignore lets only src/ and the licences through)

# The frontend is plain files: built once on the build machine, shared by every platform.
FROM --platform=$BUILDPLATFORM node:24.21-slim AS frontend
WORKDIR /build
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci
COPY src/frontend/ ./
RUN npm run build

FROM python:3.13-slim AS runtime
# Backups call pg_dump/pg_restore/psql (ADR 0018); the client must be at least the server's
# major version (PostgreSQL 18 on Unraid), so it comes from the PostgreSQL repository.
ARG PG_MAJOR=18
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl postgresql-common \
 && /usr/share/postgresql-common/pgdg/apt.postgresql.org.sh -y \
 && apt-get install -y --no-install-recommends postgresql-client-${PG_MAJOR} \
 && apt-get purge -y --auto-remove curl \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    DATA_DIR=/data BACKUP_DIR=/backups FRONTEND_DIST=/app/frontend/dist APP_ENV=production
WORKDIR /app/backend
COPY src/backend/pyproject.toml src/backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/backend/ ./
COPY --from=frontend /build/dist /app/frontend/dist
# AGPL-3.0 and the third-party licences travel with the image
COPY LICENSE THIRD-PARTY-NOTICES.md /app/

ARG APP_VERSION=0.0.0-dev
ENV APP_VERSION=$APP_VERSION
LABEL org.opencontainers.image.title="owncryptofolio" \
      org.opencontainers.image.description="Self-hosted crypto portfolio tracker with German tax reports" \
      org.opencontainers.image.source="https://github.com/Vanixxx/owncryptofolio" \
      org.opencontainers.image.licenses="AGPL-3.0-only" \
      org.opencontainers.image.version=$APP_VERSION

# Not root: the app runs as its own user (ADR 0016). The entrypoint starts as root only to
# hand mounted folders to that user (PUID/PGID), then drops root before the app starts.
RUN groupadd --system --gid 1000 app \
 && useradd --system --uid 1000 --gid 1000 --home /app app && mkdir -p /data /backups && chown app:app /data /backups
COPY --chmod=755 src/docker/entrypoint.sh /usr/local/bin/entrypoint.sh
ENV HOME=/app
VOLUME /data
EXPOSE 8080
# Docker's own check uses the same probe as the UI: a real database round trip.
HEALTHCHECK --interval=60s --timeout=10s --start-period=120s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=8).status == 200 else 1)"
# First start runs inside the app: wait for DB, create, migrate, keys (ADR 0030).
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
