# ╔══════════════════════════════════════════════════════════════╗
# ║  TREVLIX v1.0.0 – Dockerfile                                ║
# ║  Build:  docker build -t trevlix .                           ║
# ║  Run:    docker run -p 5000:5000 --env-file .env trevlix     ║
# ╚══════════════════════════════════════════════════════════════╝

FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc g++ curl \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# App directory
WORKDIR /app

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Optional: TensorFlow (uncomment to enable LSTM + Transformer)
# RUN pip install --no-cache-dir tensorflow

# Copy application files
COPY server.py .
COPY ai_engine.py .
COPY trevlix_i18n.py .
COPY trevlix_translations.js .
COPY dashboard.html .
COPY index.html .
COPY INSTALLATION.html .

# Create required directories
RUN mkdir -p /app/backups /app/logs

# Expose dashboard port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:5000/api/v1/update/status || exit 1

# Start bot
CMD ["python", "server.py"]
