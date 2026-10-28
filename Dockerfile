# Dockerfile — SIMKEU Kecamatan Candisari 2027
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (entrypoint, pages, db, assets, config)
COPY streamlit_app.py .
COPY db.py .
COPY app_pages/ ./app_pages/
COPY images/ ./images/
COPY .streamlit/config.toml .streamlit/config.toml
COPY secrets.toml.example .streamlit/secrets.toml.example

# secrets.toml diisi melalui volume / environment saat runtime (jangan copy file asli)
EXPOSE 8501

# Healthcheck agar orchestration mengetahui siap tidak
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# Jalankan aplikasi
ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.headless", "true", "--server.port", "8501", "--server.address", "0.0.0.0"]
