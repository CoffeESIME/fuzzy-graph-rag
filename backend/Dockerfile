# ──────────────────────────────────────────────
# Stage 1: Builder – instala dependencias Poetry
# ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.2 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

# Instalar curl y luego Poetry con el instalador oficial
# (pip install poetry NO respeta POETRY_HOME)
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && apt-get purge -y curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar solo manifests primero para aprovechar la caché de capas
COPY pyproject.toml poetry.lock ./

# Instalar dependencias (sin dev)
RUN $POETRY_HOME/bin/poetry install --no-root --only main

# ──────────────────────────────────────────────
# Stage 2: Runtime – imagen final ligera
# ──────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copiar el virtualenv desde el builder
COPY --from=builder /app/.venv /app/.venv

# Copiar el código fuente
COPY . .

EXPOSE 8000

# CMD por defecto: FastAPI server.
# El servicio `worker` en docker-compose sobreescribe este CMD.
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
