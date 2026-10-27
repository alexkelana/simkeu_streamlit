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

# Copy application code
COPY app.py .
COPY secrets.toml.example .streamlit/secrets.toml.example

# Expose Streamlit port
EXPOSE 8501

# Jalankan aplikasi
CMD ["streamlit", "run", "app.py", "--server.headless", "true", "--server.port", "8501"]
