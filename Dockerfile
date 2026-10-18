FROM python:3.13-slim

ARG VERSION=dev
ARG BUILD_ID=unknown
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH" \
    VERSION=${VERSION} \
    BUILD_ID=${BUILD_ID}

# Pinned uv (not :latest) so the image build is reproducible.
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
WORKDIR /app

# Dependencies first (cached unless the lockfile changes).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

# collectstatic at build time with DEBUG unset (manifest storage). The values on this
# line are build-only dummies; real secrets only ever come from the runtime environment.
RUN SECRET_KEY=build-only-not-a-secret GOOGLE_CLIENT_ID=x GOOGLE_CLIENT_SECRET=x \
    python manage.py collectstatic --noinput

# Keep -m: gunicorn creates a control socket under $HOME.
RUN useradd -m -u 1000 app && mkdir -p /app/data && chown app:app /app/data
USER app

EXPOSE 8000

# exec so SIGTERM reaches gunicorn; 2 sync workers suit SQLite's single writer.
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn web.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile - --error-logfile -"]
