# QuickChat Unified Server — Chat API + Voice Agent

Single FastAPI server combining the chat REST API (for web widgets) and the Twilio ConversationRelay voice agent. Both share one startup warmup that loads embeddings and warms the business cache.

## Architecture

```
                         Twilio ConversationRelay
  Customer Phone ──▶ Twilio Voice ──┬── Deepgram Nova-3 (STT) ──▶ text
                                    │
                                    └── Google TTS ◀── text ◀──┐
                                                                │
  Web Widget ──▶ POST /chat                                     │
       │                                                        │
       ▼                                                        │
  ┌──────────────────────────────────────────────────────────────┘
  │
  │  server.py (FastAPI)
  │
  │  Startup warmup:
  │    Load embeddings + warm business cache (once)
  │
  │  POST /chat            → Chat API for web widget
  │  POST /incoming-call   → TwiML (connect WebSocket)
  │  WS   /voice-ws        → ConversationRelay handler
  │  GET  /health          → Health check
  │         │
  │         ▼
  │  app.api.process_query()  (shared RAG pipeline)
  │    Supervisor → Router → Operator → Generator
  │    (LangGraph + ChromaDB)
  │         │
  │         ▼ (voice only)
  │  voice_utils.format_for_voice()
  │    Strip markdown, truncate to ~75 words
  └──────────────────────────────────────────────────────────────
```

## File Structure

```
server.py                 # Unified FastAPI server
voice_utils.py            # Voice response formatting
config/phone_mapping.json # Phone number → business mapping
requirements.txt          # All dependencies (core + server)
start.sh                  # Docker/HF Spaces startup script
Dockerfile                # Container build (HF Spaces compatible)
.env.example              # Environment variable template
scripts/deploy_hf_space.sh# HF Spaces deploy helper
test_chat_api.py          # Chat endpoint test
test_voice_local.py       # Voice WebSocket test (no Twilio needed)
README_SERVER.md          # This file
```

## Prerequisites

- Python 3.10+
- Existing QuickChat app with ChromaDB data loaded
- Twilio account with a phone number (for voice in production)
- Deepgram API key (configured in Twilio ConversationRelay)
- ngrok or similar tunnel (for local voice development)

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure phone number mapping

Edit `config/phone_mapping.json` to map your Twilio phone numbers to businesses:

```json
{
  "phone_numbers": {
    "+1XXXXXXXXXX": {
      "business_id": "Sawan Indian Cuisine",
      "greeting": "Thank you for calling Sawan Indian Cuisine! How can I help you?"
    }
  },
  "default_greeting": "Thank you for calling! How can I help you today?",
  "default_business_id": null
}
```

### 3. Set environment variables

```bash
# Required for voice in production (your public-facing hostname)
export VOICE_WS_HOST="your-domain.ngrok.io"

# Optional overrides
export CHROMA_PERSIST_PATH="./data/chroma"
export CR_VOICE="Google.en-US-Standard-J"
export CR_LANGUAGE="en-US"
export CR_TRANSCRIPTION_PROVIDER="deepgram"
export CR_SPEECH_MODEL="nova-3"
export CR_TTS_PROVIDER="google"
```

### 4. Start the server

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### 5. Test the chat API

```bash
# Health check
curl http://localhost:8000/health

# Chat query
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"business_id": "Sawan Indian Cuisine", "query": "What are your hours?"}'

# Or run the test script
python test_chat_api.py
```

### 6. Test voice locally (no Twilio required)

```bash
python test_voice_local.py
```

### 7. Expose via ngrok (for Twilio voice)

```bash
ngrok http 8000
```

Configure your Twilio phone number webhook to `https://YOUR-NGROK-URL/incoming-call` (HTTP POST).

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Chat API for web widgets |
| POST | `/incoming-call` | Twilio voice webhook (returns TwiML) |
| WS | `/voice-ws` | ConversationRelay WebSocket handler |
| GET | `/health` | Health check |

### POST /chat

Request body:
```json
{
  "business_id": "Sawan Indian Cuisine",
  "query": "What are your hours?",
  "chat_history": [],
  "user_id": "anonymous"
}
```

Response:
```json
{
  "answer": "We are open from 11am to 10pm daily.",
  "sources": ["menu.pdf"]
}
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | LLM backend: `ollama` (local) or `groq` (cloud) |
| `GROQ_API_KEY` | — | Required when `LLM_PROVIDER=groq` |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `CHROMA_PERSIST_PATH` | `./data/chroma` | Path to ChromaDB persistence directory |
| `SERVER_PORT` | `8000` | FastAPI server port |
| `VOICE_WS_HOST` | (from request Host header) | Public hostname for WebSocket URL in TwiML |
| `PHONE_MAPPING_PATH` | `config/phone_mapping.json` | Path to phone mapping config |
| `CR_VOICE` | `Google.en-US-Standard-J` | TTS voice for ConversationRelay |
| `CR_LANGUAGE` | `en-US` | Language code |
| `CR_TRANSCRIPTION_PROVIDER` | `deepgram` | STT provider |
| `CR_SPEECH_MODEL` | `nova-3` | Deepgram speech model |
| `CR_TTS_PROVIDER` | `google` | TTS provider |

## Deploy to Hugging Face Spaces

### 1. Set Space Secrets

In your HF Space settings (Settings → Repository Secrets), add:

| Secret | Value |
|---|---|
| `LLM_PROVIDER` | `groq` |
| `GROQ_API_KEY` | `gsk_your_key_here` |

### 2. Deploy

```bash
scripts/deploy_hf_space.sh <hf-username> <space-name>
```

This pushes the code to your HF Space, which triggers a Docker build. On startup:
1. Documents are ingested into ChromaDB (if not already done)
2. FastAPI server starts on port 8000 (chat API + voice WebSocket)
3. Streamlit starts on port 7860 (HF Spaces' exposed port — the demo UI)

### 3. What's accessible

- **Streamlit demo**: `https://huggingface.co/spaces/<user>/<space>` (public)
- **Chat API**: `POST /chat` on port 8000 (internal to container)
- **Voice WebSocket**: `WS /voice-ws` on port 8000 (internal to container)

> **Note**: HF Spaces only exposes port 7860. The FastAPI server on port 8000 is for
> internal use within the container. For external API access with voice/chat endpoints,
> deploy to a VPS or cloud platform (AWS, GCP, Railway, etc.).
