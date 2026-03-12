#!/usr/bin/env bash
# Startup script for Hugging Face Spaces (Docker SDK).
#
# 1. Ingest documents into ChromaDB if not already present.
# 2. Start the unified FastAPI server (chat API + voice) on port 8000.
# 3. Start Streamlit on port 7860 (HF Spaces' exposed port).
#
# Environment variables (set as HF Space Secrets):
#   LLM_PROVIDER   — "groq" (recommended for HF) or "ollama" (local only)
#   GROQ_API_KEY   — Required when LLM_PROVIDER=groq
#   GROQ_MODEL     — Optional, defaults to llama-3.3-70b-versatile
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

# ── Step 2: Start FastAPI server in background ─────────────────────────
echo "[startup] Starting FastAPI server on port 8000..."
uvicorn server:app --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!
echo "[startup] FastAPI PID: $FASTAPI_PID"

# ── Step 3: Start Streamlit on port 7860 (HF Spaces' exposed port) ────
echo "[startup] Starting Streamlit on port 7860..."
exec streamlit run app/streamlit_app.py \
    --server.port=7860 \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --browser.gatherUsageStats=false
