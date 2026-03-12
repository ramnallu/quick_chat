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
requirements-server.txt   # Server dependencies
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
pip install -r requirements-server.txt
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
| `CHROMA_PERSIST_PATH` | `./data/chroma` | Path to ChromaDB persistence directory |
| `VOICE_WS_HOST` | (from request Host header) | Public hostname for WebSocket URL in TwiML |
| `PHONE_MAPPING_PATH` | `config/phone_mapping.json` | Path to phone mapping config |
| `CR_VOICE` | `Google.en-US-Standard-J` | TTS voice for ConversationRelay |
| `CR_LANGUAGE` | `en-US` | Language code |
| `CR_TRANSCRIPTION_PROVIDER` | `deepgram` | STT provider |
| `CR_SPEECH_MODEL` | `nova-3` | Deepgram speech model |
| `CR_TTS_PROVIDER` | `google` | TTS provider |
