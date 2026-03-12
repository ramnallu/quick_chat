# QuickChat Voice Agent — Twilio ConversationRelay

Phone/voice AI agent for QuickChat using Twilio ConversationRelay, Deepgram STT, and Google TTS. Reuses the existing LangGraph + ChromaDB RAG pipeline — no vendor lock-in.

## Architecture

```
                         Twilio ConversationRelay
  Customer Phone ──▶ Twilio Voice ──┬── Deepgram Nova-3 (STT) ──▶ text
                                    │
                                    └── Google TTS ◀── text ◀──┐
                                                                │
                     ┌──────────────────────────────────────────┘
                     │
  ┌──────────────────▼───────────────────────────────────┐
  │  voice_server.py (FastAPI)                           │
  │                                                      │
  │  POST /incoming-call   → TwiML (connect WebSocket)   │
  │  WS   /voice-ws        → ConversationRelay handler   │
  │         │                                            │
  │         ▼                                            │
  │  phone_mapping.json → resolve business               │
  │         │                                            │
  │         ▼                                            │
  │  app.api.process_query()  (existing RAG pipeline)    │
  │    Supervisor → Router → Operator → Generator        │
  │    (LangGraph + ChromaDB)                            │
  │         │                                            │
  │         ▼                                            │
  │  voice_utils.format_for_voice()                      │
  │    Strip markdown, truncate to ~75 words             │
  └──────────────────────────────────────────────────────┘
```

## File Structure

```
voice_server.py          # FastAPI: /incoming-call + /voice-ws
voice_utils.py           # Response formatting for speech
config/phone_mapping.json # Phone number → business mapping
requirements-voice.txt   # Voice-specific dependencies
test_voice_local.py      # Local WebSocket test (no Twilio needed)
README_VOICE.md          # This file
```

## Prerequisites

- Python 3.10+
- Existing QuickChat app with ChromaDB data loaded
- Twilio account with a phone number (for production)
- Deepgram API key (configured in Twilio ConversationRelay)
- ngrok or similar tunnel (for local development)

## Setup

### 1. Install voice dependencies

```bash
pip install -r requirements-voice.txt
```

### 2. Configure phone number mapping

Edit `config/phone_mapping.json` to map your Twilio phone numbers to businesses:

```json
{
  "phone_numbers": {
    "+1XXXXXXXXXX": {
      "business_id": "sawan indian cuisine",
      "greeting": "Thank you for calling Sawan Indian Cuisine! How can I help you?"
    }
  },
  "default_greeting": "Thank you for calling! How can I help you today?",
  "default_business_id": null
}
```

The `business_id` must match the ChromaDB collection directory name (lowercase).

### 3. Set environment variables

```bash
# Required for production (your public-facing hostname)
export VOICE_WS_HOST="your-domain.ngrok.io"

# Optional overrides
export CR_VOICE="Google.en-US-Standard-J"
export CR_LANGUAGE="en-US"
export CR_TRANSCRIPTION_PROVIDER="deepgram"
export CR_SPEECH_MODEL="nova-3"
export CR_TTS_PROVIDER="google"
```

### 4. Start the voice server

```bash
uvicorn voice_server:app --host 0.0.0.0 --port 8765
```

### 5. Expose via ngrok (local development)

```bash
ngrok http 8765
```

### 6. Configure Twilio

1. Go to your Twilio Console → Phone Numbers
2. Select your number → Voice Configuration
3. Set "A Call Comes In" webhook to: `https://YOUR-NGROK-URL/incoming-call` (HTTP POST)
4. Save

### 7. Test locally (no Twilio required)

```bash
# In terminal 1 — start the server
uvicorn voice_server:app --host 0.0.0.0 --port 8765

# In terminal 2 — run the test client
python test_voice_local.py
```

The test client simulates ConversationRelay messages (setup → prompt → prompt → interrupt) and prints all responses.

## How It Works

1. **Incoming call** — Twilio POSTs to `/incoming-call`. The server returns TwiML that tells Twilio to use ConversationRelay with Deepgram STT and Google TTS, connecting to the `/voice-ws` WebSocket.

2. **Setup** — Twilio opens the WebSocket and sends a `setup` message with the call SID and phone numbers. The server resolves the dialled number to a business via `phone_mapping.json` and sends the greeting.

3. **Conversation** — Twilio sends `prompt` messages containing the caller's transcribed speech. The server runs each through `process_query()` (the same RAG pipeline as the chat widget), formats the response for voice, and sends it back. Twilio speaks it using Google TTS.

4. **Interruption** — If the caller speaks while the agent is talking, Twilio sends an `interrupt` message. The server cancels any in-progress query.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `VOICE_WS_HOST` | (from request Host header) | Public hostname for WebSocket URL in TwiML |
| `PHONE_MAPPING_PATH` | `config/phone_mapping.json` | Path to phone mapping config |
| `CR_VOICE` | `Google.en-US-Standard-J` | TTS voice for ConversationRelay |
| `CR_LANGUAGE` | `en-US` | Language code |
| `CR_TRANSCRIPTION_PROVIDER` | `deepgram` | STT provider |
| `CR_SPEECH_MODEL` | `nova-3` | Deepgram speech model |
| `CR_TTS_PROVIDER` | `google` | TTS provider |

## Phase 2 Roadmap

- **Self-hosted Kokoro TTS** — Replace Google TTS with open-source Kokoro (82M params, Apache 2.0, runs on CPU) to eliminate per-minute TTS costs
- **DTMF menu** — Route callers via keypad (e.g., "Press 1 for hours, 2 for directions")
- **Call analytics** — Log call duration, query topics, and satisfaction signals
- **Multi-language** — Swap STT/TTS language per business
