# QuickChat Voice Agent — Retell AI Integration

This adds a voice/phone AI agent to QuickChat. Customers can call a Retell AI phone number and get answers from the **same** ChromaDB knowledge base that powers the chat widget — no duplicated RAG logic.

## Architecture

```
Customer Phone Call
        │
        ▼
   Retell AI (STT)
        │  WebSocket
        ▼
  voice_server.py          ◄── FastAPI WebSocket server
        │
        ▼
  retell_handler.py        ◄── Protocol parsing, phone→business mapping
        │
        ▼
  app.api.process_query()  ◄── EXISTING QuickChat RAG pipeline (reused)
        │
        ▼
  voice_utils.py           ◄── Strip markdown, truncate for speech
        │
        ▼
   Retell AI (TTS)
        │
        ▼
  Customer hears response
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt -r requirements-voice.txt
```

### 2. Ingest business documents (if not done already)

```bash
python scripts/ingest_documents.py --source-dir ./data --chroma-persist ./data/chroma
```

### 3. Configure environment

Set the same LLM environment variables used by the chat app:

```bash
# .env or export directly
export LLM_PROVIDER=groq          # or "ollama"
export GROQ_API_KEY=gsk_...       # if using Groq
export RETELL_API_KEY=ret_...     # your Retell AI API key (for webhook validation)
```

### 4. Map phone numbers to businesses

Edit `config/phone_mapping.json` and replace the placeholder phone numbers with your actual Retell phone numbers:

```json
{
    "phone_numbers": {
        "+1XXXXXXXXXX": {
            "business_id": "Sawan Indian Cuisine",
            "greeting": "Thank you for calling Sawan Indian Cuisine! How can I help you today?"
        }
    }
}
```

The `business_id` must match the business names in your ChromaDB collections (the same names shown in the Streamlit dropdown).

### 5. Start the voice server

```bash
python voice_server.py
# or
uvicorn voice_server:app --host 0.0.0.0 --port 8080
```

### 6. Configure Retell AI

1. Go to your [Retell AI Dashboard](https://www.retellai.com/)
2. Create or select an Agent
3. Under LLM settings, choose **Custom LLM**
4. Set the WebSocket URL to: `wss://<your-server>:8080/llm-websocket/{call_id}`
5. Assign a phone number to the agent
6. Add that phone number to `config/phone_mapping.json`

> **Note:** For production, you'll need HTTPS/WSS. Use a reverse proxy (nginx, Caddy) or deploy behind a cloud load balancer with TLS termination.

## Local Testing (no Retell account needed)

A test script simulates Retell WebSocket messages locally:

```bash
# Terminal 1 — start the server
python voice_server.py

# Terminal 2 — run the test client
python test_voice_ws.py

# Test a specific business
python test_voice_ws.py --business "Active Body Fitness"
python test_voice_ws.py --business "White Tiger Martial Arts"
```

The test client sends `call_details`, a `ping`, and then three sample questions, printing the voice-formatted responses.

## Files Added

| File | Purpose |
|---|---|
| `voice_server.py` | FastAPI WebSocket server (Retell Custom LLM endpoint) |
| `retell_handler.py` | Retell protocol parsing, phone→business routing, response framing |
| `voice_utils.py` | Markdown stripping, list-to-prose conversion, speech truncation |
| `config/phone_mapping.json` | Phone number → business ID mapping |
| `requirements-voice.txt` | Additional Python dependencies |
| `test_voice_ws.py` | Local test client simulating Retell messages |
| `README_VOICE.md` | This file |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VOICE_SERVER_PORT` | `8080` | Port for the FastAPI server |
| `VOICE_STREAM_RESPONSES` | `true` | Stream responses in chunks (better for voice pacing) |
| `LLM_PROVIDER` | `ollama` | Same as chat app — `groq` or `ollama` |
| `GROQ_API_KEY` | — | Required if `LLM_PROVIDER=groq` |
| `RETELL_API_KEY` | — | Your Retell AI API key |

## How It Works

1. **Retell calls your WebSocket** when a customer dials in — sends `call_details` with phone numbers
2. **Phone mapping** resolves which business the call is for via `config/phone_mapping.json`
3. **Greeting** is sent back immediately as the first agent utterance
4. **Each user utterance** triggers a `response_required` event — the server extracts the latest question, runs it through the existing `process_query()` pipeline, and formats the answer for speech
5. **Voice formatting** strips markdown, converts lists to natural prose, and truncates to ~75 words (~30 seconds of speech)
6. **Streaming** splits responses into word-chunked frames for natural TTS pacing
