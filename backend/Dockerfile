# Seekhai_test backend — FastAPI + uvicorn. All Python deps ship as wheels, so the slim base
# needs no compilers. Migrations run on startup (docker-entrypoint.sh) before the API serves.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# App source (see .dockerignore for what's excluded: .venv, caches, local data).
COPY . .
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# Basic liveness check against the root endpoint.
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/').status==200 else 1)"

ENTRYPOINT ["./docker-entrypoint.sh"]
