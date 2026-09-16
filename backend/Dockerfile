# SAT-SA backend — FastAPI + SQLite, fully offline at runtime.
# Build needs network access (pip install); the running container needs none.

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# database.py resolves the SQLite path to <backend root>/data/satsa.db —
# i.e. /app/data/satsa.db here. Create it so the named volume below has
# somewhere to mount even before the app writes to it.
RUN mkdir -p /app/data

# Security hardening: run as a non-root, non-privileged user rather than the
# container's default root. Fixed uid/gid (not just "any free one Debian's
# useradd picks") so the ownership set here is reproducible across rebuilds
# and matches what a reviewer would see on `docker inspect`/`id` in the
# running container. chown /app (not just /app/data) so the app's own source
# tree and the data directory are both owned by the user that ends up
# running the process.
#
# Volume note: docker-compose.yml mounts a named volume at /app/data. Docker
# initializes a brand-new named volume from whatever is already at that path
# in the image *at the point USER switches* — since /app/data is chown'd to
# appuser here, before USER below, the first-created volume inherits that
# ownership too, so the app can write to it as appuser without a manual
# `chmod`/init-container step.
RUN groupadd --system --gid 1000 appuser \
    && useradd --system --uid 1000 --gid appuser --home-dir /app --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
