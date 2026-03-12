# QuickChat — Unified Docker image
# Runs Streamlit (port 7860) + FastAPI chat/voice server (port 8000)
FROM python:3.10-slim

WORKDIR /app
ENV PYTHONPATH=/app

# System deps
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python deps (single requirements file)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY . .

# Ensure data and config dirs exist
RUN mkdir -p data/chroma config

# Make startup script executable
RUN chmod +x start.sh

# HF Spaces exposes port 7860 (Streamlit demo)
# FastAPI runs on port 8000 (chat API + voice WebSocket)
EXPOSE 7860 8000

ENTRYPOINT ["./start.sh"]
