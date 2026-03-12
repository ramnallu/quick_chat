#!/usr/bin/env bash
# Startup script for Hugging Face Spaces (Docker SDK).
#
# 1. Ingest documents into ChromaDB if not already present.
# 2. Start all services via supervisord:
#      - nginx on port 7860 (HF's exposed port — reverse proxy)
#      - FastAPI on port 8000 (chat API + voice WebSocket)
#      - Streamlit on port 8501 (demo UI)
#
# Nginx routes:
#   /chat, /incoming-call, /health, /voice-ws  →  FastAPI  (8000)
#   everything else                             →  Streamlit (8501)
#
# Environment variables (set as HF Space Secrets):
#   LLM_PROVIDER   — "groq" (recommended for HF) or "ollama" (local only)
#   GROQ_API_KEY   — Required when LLM_PROVIDER=groq
set -e

CHROMA_DIR="${CHROMA_PERSIST_PATH:-./data/chroma}"

echo "========================================="
echo " QuickChat Unified Startup"
echo "========================================="

# ── Step 1: Ingest documents if ChromaDB is empty ──────────────────────
if [ ! -d "$CHROMA_DIR" ] || [ -z "$(ls -A "$CHROMA_DIR" 2>/dev/null)" ]; then
    echo "[startup] ChromaDB not found — ingesting documents..."
    python scripts/ingest_documents.py --source-dir ./data --chroma-persist "$CHROMA_DIR"
    echo "[startup] Ingestion complete."
else
    echo "[startup] ChromaDB already populated at $CHROMA_DIR"
fi

# ── Step 2: Start all services ─────────────────────────────────────────
echo "[startup] Starting nginx (7860) + FastAPI (8000) + Streamlit (8501)..."
exec supervisord -c /app/config/supervisord.conf
