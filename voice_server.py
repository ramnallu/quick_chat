"""FastAPI WebSocket server implementing Retell AI's Custom LLM protocol.

This server bridges Retell AI voice calls to the existing QuickChat
LangGraph RAG pipeline.  It does NOT duplicate any retrieval or agent
logic — it imports and reuses ``app.api.process_query`` directly.

Usage:
    uvicorn voice_server:app --host 0.0.0.0 --port 8080

Retell will connect to:
    ws://<your-host>:8080/llm-websocket/<call_id>
"""

import asyncio
import json
import logging
import os
import sys
import pathlib

# Ensure project root is on sys.path so ``app.*`` imports work when
# running the server from the repo root with uvicorn.
_ROOT = pathlib.Path(__file__).parent.absolute()
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from retell_handler import (
    CallSession,
    build_agent_response,
    build_config_response,
    build_streaming_frames,
    extract_last_user_utterance,
    parse_retell_message,
    resolve_business,
    transcript_to_chat_history,
)
from app.api import process_query

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voice_server")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="QuickChat Voice Agent",
    description="Retell AI Custom LLM WebSocket server backed by QuickChat RAG",
    version="0.1.0",
)

# Track active sessions for observability
_active_sessions: dict[str, CallSession] = {}

# Configuration: whether to stream responses in chunks or send as one frame
STREAM_RESPONSES = os.environ.get("VOICE_STREAM_RESPONSES", "true").lower() == "true"


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return JSONResponse({"status": "ok", "active_calls": len(_active_sessions)})


# ---------------------------------------------------------------------------
# Retell Custom LLM WebSocket endpoint
# ---------------------------------------------------------------------------
@app.websocket("/llm-websocket/{call_id}")
async def retell_websocket(websocket: WebSocket, call_id: str):
    await websocket.accept()
    logger.info("WebSocket connected: call_id=%s", call_id)

    session: CallSession | None = None

    try:
        while True:
            raw = await websocket.receive_text()
            message = parse_retell_message(raw)
            interaction_type = message.get("interaction_type", "")

            # ----------------------------------------------------------
            # 1. Handle ping / keep-alive
            # ----------------------------------------------------------
            if interaction_type == "ping":
                await websocket.send_text(json.dumps({"interaction_type": "pong"}))
                continue

            # ----------------------------------------------------------
            # 2. Call start / config — resolve business, send greeting
            # ----------------------------------------------------------
            if interaction_type == "call_details":
                call_metadata = message.get("call", {})
                try:
                    business_id, greeting = resolve_business(call_metadata)
                except ValueError as exc:
                    logger.error("Business resolution failed: %s", exc)
                    await websocket.close(code=1008, reason=str(exc))
                    return

                session = CallSession(
                    call_id=call_id,
                    business_id=business_id,
                    greeting=greeting,
                )
                _active_sessions[call_id] = session
                logger.info(
                    "Call %s mapped to business=%s", call_id, business_id
                )

                # Send the greeting as the first agent utterance
                greeting_frame = build_config_response(session)
                await websocket.send_text(greeting_frame)
                continue

            # ----------------------------------------------------------
            # 3. update_only — acknowledge but don't respond
            # ----------------------------------------------------------
            if interaction_type == "update_only":
                # Retell sends these for partial transcripts / interruptions.
                # We update our session state but don't generate a response.
                if session and message.get("transcript"):
                    session.chat_history = transcript_to_chat_history(
                        message["transcript"]
                    )
                continue

            # ----------------------------------------------------------
            # 4. response_required — run the RAG pipeline
            # ----------------------------------------------------------
            if interaction_type == "response_required":
                if session is None:
                    # Edge case: no call_details received yet.  Try to
                    # create a default session from the call_id.
                    logger.warning(
                        "response_required before call_details for %s; "
                        "using default session",
                        call_id,
                    )
                    session = CallSession(
                        call_id=call_id,
                        business_id="Unknown",
                        greeting="Hello, how can I help you?",
                    )
                    _active_sessions[call_id] = session

                transcript = message.get("transcript", [])
                user_utterance = extract_last_user_utterance(transcript)

                if not user_utterance:
                    # Caller was silent or transcript is empty
                    fallback = "I'm sorry, I didn't catch that. Could you please repeat?"
                    rid = session.next_response_id()
                    await websocket.send_text(json.dumps({
                        "response_id": rid,
                        "content": fallback,
                        "content_complete": True,
                        "end_call": False,
                    }))
                    continue

                # Build chat history from full transcript (excluding the
                # latest user message — QuickChat expects history before
                # the current query).
                chat_history = transcript_to_chat_history(transcript[:-1])

                # Run the existing QuickChat RAG pipeline in a thread so
                # we don't block the async event loop (LangGraph / LLM
                # calls are synchronous).
                logger.info(
                    "call=%s biz=%s query=%r",
                    call_id,
                    session.business_id,
                    user_utterance,
                )
                result = await asyncio.to_thread(
                    process_query,
                    session.business_id,
                    user_utterance,
                    chat_history,
                    user_id=f"voice_{call_id}",
                )

                raw_answer = result.get("answer", "I'm sorry, I couldn't find that information.")

                # Send response — streaming or single frame
                if STREAM_RESPONSES:
                    frames = build_streaming_frames(session, raw_answer)
                    for frame in frames:
                        await websocket.send_text(frame)
                else:
                    frame = build_agent_response(session, raw_answer)
                    await websocket.send_text(frame)

                # Update local history
                session.chat_history = transcript_to_chat_history(transcript)
                continue

            # Unknown interaction type — log and ignore
            logger.warning("Unknown interaction_type=%r for call=%s", interaction_type, call_id)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: call_id=%s", call_id)
    except Exception:
        logger.exception("Unexpected error in call=%s", call_id)
    finally:
        _active_sessions.pop(call_id, None)
        logger.info("Session cleaned up: call_id=%s", call_id)


# ---------------------------------------------------------------------------
# Entry-point for ``python voice_server.py``
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("VOICE_SERVER_PORT", "8080"))
    uvicorn.run("voice_server:app", host="0.0.0.0", port=port, reload=True)
