FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry

# Copy dependency metadata first (better layer caching)
COPY pyproject.toml poetry.lock* /app/

# Install deps into the container (no venv)
RUN poetry config virtualenvs.create false \
 && poetry install --no-interaction --no-ansi --no-root

# Copy source
COPY . /app

EXPOSE 8000

# Run FastAPI webhook server
CMD ["poetry", "run", "uvicorn", "tg_bot_italian.main:api", "--host", "0.0.0.0", "--port", "8000"]
