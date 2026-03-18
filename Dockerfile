# ╔══════════════════════════════════════════════════════════════╗
# ║  TREVLIX v1.3.3 – Dockerfile                                ║
# ║  Build:  docker build -t trevlix .                           ║
# ║  Run:    docker run -p 5000:5000 --env-file .env trevlix     ║
# ╚══════════════════════════════════════════════════════════════╝

FROM python:3.11-slim AS builder

# System-Abhängigkeiten für den Build
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Dependencies zuerst (Layer-Caching optimiert)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime Image ──────────────────────────────────────────────
FROM python:3.11-slim

# Nur Runtime-Abhängigkeiten (kein gcc etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Non-root User für Sicherheit (Verbesserung #16)
RUN groupadd -r trevlix && useradd -r -g trevlix -d /app -s /sbin/nologin trevlix

WORKDIR /app

# Installierte Pakete aus Builder-Stage übernehmen
COPY --from=builder /install /usr/local

# Anwendungsdateien kopieren
COPY server.py .
COPY ai_engine.py .
COPY trevlix_i18n.py .
COPY validate_env.py .
COPY services/ ./services/
COPY routes/ ./routes/
COPY templates/ ./templates/
COPY static/ ./static/

# Verzeichnisse anlegen und Berechtigungen setzen
RUN mkdir -p /app/backups /app/logs \
    && chown -R trevlix:trevlix /app

# Als non-root User ausführen
USER trevlix

# Port exponieren
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:5000/api/v1/status || exit 1

# Bot starten – [Verbesserung #10] validate_env.py prüft Umgebungsvariablen vor Start
CMD ["sh", "-c", "python validate_env.py && python server.py"]
