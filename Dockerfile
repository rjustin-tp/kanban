FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml /app/backend/pyproject.toml
RUN uv sync --project /app/backend --no-dev

COPY backend /app/backend

WORKDIR /app/backend

EXPOSE 8000

CMD ["uv", "run", "--project", "/app/backend", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
