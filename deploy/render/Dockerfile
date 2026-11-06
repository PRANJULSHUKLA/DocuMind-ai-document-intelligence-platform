FROM node:22.22.2-bookworm-slim@sha256:9f6d5975c7dca860947d3915877f85607946403fc55349f39b4bc3688448bb6e AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_OIDC_AUTHORITY
ARG VITE_OIDC_CLIENT_ID
ARG VITE_OIDC_AUDIENCE
ENV VITE_API_BASE_URL=/api VITE_AUTH_MODE=oidc VITE_PILOT_MODE=1
RUN test -n "$VITE_OIDC_AUTHORITY" && test -n "$VITE_OIDC_CLIENT_ID" && test -n "$VITE_OIDC_AUDIENCE" && npm run build

FROM python:3.11-slim-bookworm@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHON_DOTENV_DISABLED=1
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils ca-certificates redis-server tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 documind && useradd --uid 10001 --gid documind --no-create-home documind \
    && mkdir -p /srv/uploads && chown documind:documind /srv/uploads
WORKDIR /srv/documind
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip check
COPY --chown=documind:documind app/ ./app/
COPY --chown=documind:documind deploy/production/start.py ./deploy/production/start.py
COPY --chown=documind:documind deploy/render/start.py ./deploy/render/start.py
COPY --from=frontend --chown=documind:documind /build/dist/ ./frontend-dist/
USER 10001:10001
ENTRYPOINT ["tini", "--", "python", "deploy/render/start.py"]
