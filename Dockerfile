# QuickChat — Unified Docker image for Hugging Face Spaces
# Single port 7860 serves everything via nginx reverse proxy:
#   /chat, /incoming-call, /health, /voice-ws  →  FastAPI  (8000)
#   everything else                             →  Streamlit (8501)
FROM python:3.10-slim

WORKDIR /app
ENV PYTHONPATH=/app

# System deps: build tools + nginx + supervisord
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Python deps (single requirements file)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Ensure directories exist
RUN mkdir -p data/chroma config /tmp/nginx

# Make startup script executable
RUN chmod +x start.sh

# HF Spaces exposes only port 7860 — nginx listens here
EXPOSE 7860

ENTRYPOINT ["./start.sh"]
