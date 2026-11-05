FROM python:3.11-slim-bookworm@sha256:94a8fee35252d06ab75856f15f12c7bae67b10e8a6da93c7fded82b2610926cd
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 documind && useradd --uid 10001 --gid documind --no-create-home documind \
    && mkdir -p /srv/uploads && chown documind:documind /srv/uploads
WORKDIR /srv/documind
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt && python -m pip check
COPY --chown=documind:documind app ./app
COPY --chown=documind:documind deploy/production/start.py deploy/production/readiness.py ./deploy/production/
USER 10001:10001
ENTRYPOINT ["python", "deploy/production/start.py"]
CMD ["api"]
