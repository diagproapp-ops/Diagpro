FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    libreoffice-writer \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY core /app/core
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini

RUN useradd -m -u 10001 diagpro && \
    mkdir -p /app/avatars /app/static /app/ProvasGeradas_DG /app/templates_eventos && \
    chown -R diagpro:diagpro /app

USER diagpro

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
