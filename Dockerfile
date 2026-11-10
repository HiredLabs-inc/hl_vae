# The VAE web image (DES-008). Cloud Run runs it as the web service and as the
# migrate/manage jobs. It holds no credentials and no secrets: on Cloud Run the
# runtime service account is reached through the metadata server, and settings
# come from env vars plus Secret Manager (hl_vae/settings/cloud.py).
#
# To run it locally against Postgres, see "Docker image" in README.md.

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so code changes don't reinstall them. The project itself
# isn't installed: the code runs from /app, so BASE_DIR (and STATIC_ROOT) is
# /app. Only [project] dependencies are installed, not the dev extra.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY . .

# collectstatic needs no secrets or database, so it uses the build-only
# settings, which inherit the static settings cloud.py serves (DES-006).
RUN DJANGO_SETTINGS_MODULE=hl_vae.settings.build python manage.py collectstatic --noinput

RUN useradd --system --no-create-home app
USER app

# DJANGO_SETTINGS_MODULE is deliberately not set here: Cloud Run sets it, and
# wsgi.py refuses to start without it.
# One worker with 8 threads per instance; Cloud Run scales instances. Timeout 0
# leaves request timeouts to Cloud Run. The control socket (gunicorn 26+) is
# unused on Cloud Run and would need a writable home directory.
ENV PORT=8080
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 0 --no-control-socket hl_vae.wsgi:application"]
