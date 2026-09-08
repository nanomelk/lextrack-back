# ── Etapa 1: Compilación de dependencias ──────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Copiar manifiesto de dependencias
COPY requirements.txt .

# Instalar dependencias en un directorio prefijo
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Etapa 2: Imagen de producción ────────────────────────────────
FROM python:3.11-slim AS production

LABEL maintainer="LexTrack"
LABEL description="Backend FastAPI — Sistema de Gestión de Casos Jurídicos"
LABEL version="1.0.0"

WORKDIR /app

# Copiar dependencias instaladas desde el builder
COPY --from=builder /install /usr/local

# Copiar todo el contenido de 'backend' respetando la estructura interna
COPY . .

# Variables de entorno
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]

