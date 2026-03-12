"""Unified FastAPI server: Chat REST API + Twilio Voice Agent.

Endpoints:
    POST /chat           – Chat API for web widget
    POST /incoming-call  – Returns TwiML connecting Twilio to our WebSocket
    WS   /voice-ws       – Handles ConversationRelay messages
    GET  /health         – Health check

Run:
    uvicorn server:app --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.api import process_query, warmup_business_cache
from voice_utils import format_for_voice

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("server")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CHROMA_PERSIST = os.environ.get("CHROMA_PERSIST_PATH", "./data/chroma")

PHONE_MAPPING_PATH = os.environ.get(
    "PHONE_MAPPING_PATH",
    str(Path(__file__).resolve().parent / "config" / "phone_mapping.json"),
)

VOICE_WS_HOST = os.environ.get("VOICE_WS_HOST", "")
VOICE_WS_PATH = "/voice-ws"

# ConversationRelay TTS / STT settings
CR_VOICE = os.environ.get("CR_VOICE", "Google.en-US-Standard-J")
CR_LANGUAGE = os.environ.get("CR_LANGUAGE", "en-US")
CR_TRANSCRIPTION_PROVIDER = os.environ.get("CR_TRANSCRIPTION_PROVIDER", "deepgram")
CR_SPEECH_MODEL = os.environ.get("CR_SPEECH_MODEL", "nova-3")
CR_TTS_PROVIDER = os.environ.get("CR_TTS_PROVIDER", "google")


def _load_phone_mapping() -> dict:
    try:
        with open(PHONE_MAPPING_PATH) as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("Phone mapping file not found at %s – using empty mapping", PHONE_MAPPING_PATH)
        return {"phone_numbers": {}, "default_greeting": "Thank you for calling! How can I help you?", "default_business_id": None}


PHONE_MAPPING = _load_phone_mapping()


def _resolve_business(to_number: str) -> tuple[str | None, str]:
    """Return (business_id, greeting) for the dialled number."""
    entry = PHONE_MAPPING["phone_numbers"].get(to_number)
    if entry:
        return entry["business_id"], entry.get("greeting", PHONE_MAPPING["default_greeting"])
    return PHONE_MAPPING.get("default_business_id"), PHONE_MAPPING["default_greeting"]


def _list_businesses(chroma_persist_path: str) -> list[str]:
    """Discover businesses from ChromaDB collections."""
    try:
        client = chromadb.PersistentClient(path=chroma_persist_path)
        collections = client.list_collections()
        items = []
        for col in collections:
            name = col.name
            if name.startswith("business__"):
                name = name.replace("business__", "").replace("_", " ").title()
            items.append(name)
        return sorted(items)
    except Exception as e:
        logger.warning("Error listing businesses from ChromaDB: %s", e)
        return []


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="QuickChat Unified Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup warmup
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def warmup():
    """Load embeddings and warm up business cache once at startup."""
    logger.info("Starting warmup...")

    # Discover businesses from phone mapping
    phone_businesses = [
        entry["business_id"]
        for entry in PHONE_MAPPING["phone_numbers"].values()
    ]

    # Discover businesses from ChromaDB
    chroma_businesses = _list_businesses(CHROMA_PERSIST)

    # Combine and deduplicate
    all_businesses = list(set(phone_businesses + chroma_businesses))

    if all_businesses:
        logger.info("Warming up cache for %d businesses: %s", len(all_businesses), all_businesses)
        await asyncio.to_thread(warmup_business_cache, all_businesses)
        logger.info("Warmup complete")
    else:
        logger.warning("No businesses found for warmup")


# ---------------------------------------------------------------------------
# Chat REST API
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    business_id: str
    query: str
    chat_history: list = []
    user_id: str = "anonymous"


@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat endpoint for web widget."""
    logger.info("Chat request for business=%s query=%s", request.business_id, request.query[:100])

    result = await asyncio.to_thread(
        process_query,
        request.business_id,
        request.query,
        request.chat_history,
        request.user_id,
    )

    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
    }


# ---------------------------------------------------------------------------
# Voice: POST /incoming-call
# ---------------------------------------------------------------------------

@app.post("/incoming-call")
async def incoming_call(request: Request):
    """Twilio webhook: return TwiML that starts a ConversationRelay session."""
    form = await request.form()
    to_number = form.get("To", "")
    logger.info("Incoming call to %s", to_number)

    ws_host = VOICE_WS_HOST
    if not ws_host:
        host_header = request.headers.get("host", "localhost:8000")
        ws_host = host_header

    ws_url = f"wss://{ws_host}{VOICE_WS_PATH}"

    response = VoiceResponse()
    connect = Connect()
    connect.conversation_relay(
        url=ws_url,
        dtmf_detection="true",
        voice=CR_VOICE,
        language=CR_LANGUAGE,
        transcription_provider=CR_TRANSCRIPTION_PROVIDER,
        speech_model=CR_SPEECH_MODEL,
        tts_provider=CR_TTS_PROVIDER,
    )
    response.append(connect)

    return Response(content=str(response), media_type="application/xml")


# ---------------------------------------------------------------------------
# Voice: WebSocket handler
# ---------------------------------------------------------------------------

class VoiceSession:
    """Per-call state for a ConversationRelay session."""

    def __init__(self, websocket: WebSocket):
        self.ws = websocket
        self.call_sid: str = ""
        self.from_number: str = ""
        self.to_number: str = ""
        self.business_id: str | None = None
        self.greeting: str = ""
        self.chat_history: list[dict] = []
        self._current_task: asyncio.Task | None = None

    async def send_text(self, text: str) -> None:
        msg = json.dumps({"type": "text", "token": text})
        await self.ws.send_text(msg)

    async def send_end(self) -> None:
        msg = json.dumps({"type": "end"})
        await self.ws.send_text(msg)

    def cancel_pending(self) -> None:
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            self._current_task = None


@app.websocket(VOICE_WS_PATH)
async def voice_ws(websocket: WebSocket):
    await websocket.accept()
    session = VoiceSession(websocket)
    logger.info("WebSocket connected")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Non-JSON message received: %s", raw[:200])
                continue

            msg_type = msg.get("type", "")

            if msg_type == "setup":
                await _handle_setup(session, msg)

            elif msg_type == "prompt":
                session.cancel_pending()
                session._current_task = asyncio.create_task(
                    _handle_prompt(session, msg)
                )

            elif msg_type == "interrupt":
                session.cancel_pending()
                logger.info("[%s] Caller interrupted", session.call_sid)

            elif msg_type == "dtmf":
                digit = msg.get("digit", "")
                logger.info("[%s] DTMF digit: %s", session.call_sid, digit)

            else:
                logger.debug("[%s] Unhandled message type: %s", session.call_sid, msg_type)

    except WebSocketDisconnect:
        logger.info("[%s] WebSocket disconnected", session.call_sid)
    except Exception:
        logger.exception("Unexpected error in voice WebSocket")
    finally:
        session.cancel_pending()


# ---------------------------------------------------------------------------
# Voice: Message handlers
# ---------------------------------------------------------------------------

async def _handle_setup(session: VoiceSession, msg: dict) -> None:
    session.call_sid = msg.get("callSid", "")
    session.from_number = msg.get("from", "")
    session.to_number = msg.get("to", "")

    session.business_id, session.greeting = _resolve_business(session.to_number)

    logger.info(
        "Setup – call_sid=%s from=%s to=%s business=%s",
        session.call_sid, session.from_number, session.to_number, session.business_id,
    )

    await session.send_text(session.greeting)


async def _handle_prompt(session: VoiceSession, msg: dict) -> None:
    user_text = msg.get("voicePrompt", "").strip()
    if not user_text:
        return

    logger.info("[%s] User said: %s", session.call_sid, user_text)

    if not session.business_id:
        await session.send_text(
            "I'm sorry, I'm not sure which business you're trying to reach. Please try again later."
        )
        return

    try:
        result = await asyncio.to_thread(
            process_query,
            session.business_id,
            user_text,
            session.chat_history,
        )

        answer = result.get("answer", "I'm sorry, I couldn't find an answer to that.")
        voice_answer = format_for_voice(answer)

        session.chat_history.append({"role": "user", "content": user_text})
        session.chat_history.append({"role": "assistant", "content": voice_answer})

        await session.send_text(voice_answer)
        logger.info("[%s] Agent replied: %s", session.call_sid, voice_answer[:120])

    except asyncio.CancelledError:
        logger.info("[%s] Prompt handling cancelled (interrupted)", session.call_sid)
    except Exception:
        logger.exception("[%s] Error processing prompt", session.call_sid)
        await session.send_text("I'm sorry, something went wrong. Please try again.")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "quickchat-unified-server"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
