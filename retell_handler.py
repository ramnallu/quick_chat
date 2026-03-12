"""Retell AI Custom LLM WebSocket protocol handler.

Parses incoming Retell messages, maps calls to businesses via phone number,
converts the Retell transcript format into the QuickChat agent's expected
input, and builds Retell-compatible response frames.

Reference: https://docs.retellai.com/api-references/llm-websocket
"""

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from voice_utils import format_for_voice


# ---------------------------------------------------------------------------
# Phone → Business mapping
# ---------------------------------------------------------------------------

def load_phone_mapping(path: str = None) -> dict:
    """Load the phone-number-to-business mapping from JSON config."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), "config", "phone_mapping.json")
    with open(path, "r") as f:
        return json.load(f)


_PHONE_MAP: dict | None = None


def get_phone_mapping() -> dict:
    global _PHONE_MAP
    if _PHONE_MAP is None:
        _PHONE_MAP = load_phone_mapping()
    return _PHONE_MAP


def resolve_business(call_metadata: dict) -> tuple[str, str]:
    """Determine the business_id and greeting for an incoming call.

    Args:
        call_metadata: Dict that may contain ``from_number``, ``to_number``,
            or an explicit ``business_id`` override.

    Returns:
        (business_id, greeting) — the greeting is suitable as the agent's
        first spoken message.
    """
    mapping = get_phone_mapping()
    phone_numbers = mapping.get("phone_numbers", {})

    # Check explicit override first (useful for testing)
    if call_metadata.get("business_id"):
        biz_id = call_metadata["business_id"]
        for entry in phone_numbers.values():
            if entry["business_id"] == biz_id:
                return biz_id, entry.get("greeting", mapping["default_greeting"])
        return biz_id, mapping["default_greeting"]

    # Try to_number (the business's Retell number the customer dialled)
    to_number = call_metadata.get("to_number", "")
    if to_number in phone_numbers:
        entry = phone_numbers[to_number]
        return entry["business_id"], entry.get("greeting", mapping["default_greeting"])

    # Try from_number as fallback (less common)
    from_number = call_metadata.get("from_number", "")
    if from_number in phone_numbers:
        entry = phone_numbers[from_number]
        return entry["business_id"], entry.get("greeting", mapping["default_greeting"])

    # No match — use default if configured
    default_biz = mapping.get("default_business_id")
    if default_biz:
        return default_biz, mapping["default_greeting"]

    raise ValueError(
        f"Cannot resolve business for call. to_number={to_number!r}, "
        f"from_number={from_number!r}. Configure config/phone_mapping.json."
    )


# ---------------------------------------------------------------------------
# Call session state
# ---------------------------------------------------------------------------

@dataclass
class CallSession:
    """Tracks per-call state during a Retell WebSocket session."""
    call_id: str
    business_id: str
    greeting: str
    response_id_counter: int = 0
    chat_history: list = field(default_factory=list)

    def next_response_id(self) -> int:
        rid = self.response_id_counter
        self.response_id_counter += 1
        return rid


# ---------------------------------------------------------------------------
# Retell message parsing
# ---------------------------------------------------------------------------

def parse_retell_message(raw: str) -> dict:
    """Parse an incoming Retell WebSocket JSON message."""
    return json.loads(raw)


def extract_last_user_utterance(transcript: list[dict]) -> Optional[str]:
    """Pull the most recent user utterance from the Retell transcript.

    Retell sends the full transcript each time. We only need the latest
    user message to feed into the QuickChat pipeline — the pipeline has
    its own chat_history management.
    """
    for entry in reversed(transcript):
        if entry.get("role") == "user":
            content = entry.get("content", "").strip()
            if content:
                return content
    return None


def transcript_to_chat_history(transcript: list[dict]) -> list[dict]:
    """Convert Retell transcript format to QuickChat chat_history format.

    Retell: [{"role": "agent"|"user", "content": "..."}]
    QuickChat: [{"role": "assistant"|"user", "text": "..."}]
    """
    history = []
    for entry in transcript:
        role = "assistant" if entry.get("role") == "agent" else "user"
        text = entry.get("content", "")
        if text.strip():
            history.append({"role": role, "text": text})
    return history


# ---------------------------------------------------------------------------
# Retell response frame builders
# ---------------------------------------------------------------------------

def build_response_frame(
    response_id: int,
    content: str,
    content_complete: bool = True,
    end_call: bool = False,
) -> str:
    """Build a JSON response frame for Retell."""
    return json.dumps({
        "response_id": response_id,
        "content": content,
        "content_complete": content_complete,
        "end_call": end_call,
    })


def build_config_response(session: CallSession) -> str:
    """Build the initial config/greeting response when a call connects."""
    rid = session.next_response_id()
    return build_response_frame(
        response_id=rid,
        content=session.greeting,
        content_complete=True,
        end_call=False,
    )


def build_agent_response(session: CallSession, raw_answer: str) -> str:
    """Format a RAG pipeline answer into a Retell response frame.

    Applies voice formatting (strip markdown, truncate, etc.) before
    sending.
    """
    voice_text = format_for_voice(raw_answer)
    rid = session.next_response_id()
    return build_response_frame(
        response_id=rid,
        content=voice_text,
        content_complete=True,
        end_call=False,
    )


def build_streaming_frames(session: CallSession, raw_answer: str, chunk_words: int = 8) -> list[str]:
    """Split a response into streaming frames for more natural voice pacing.

    Returns a list of JSON strings — send them sequentially over the
    WebSocket. The last frame has ``content_complete=True``.
    """
    voice_text = format_for_voice(raw_answer)
    words = voice_text.split()
    rid = session.next_response_id()
    frames = []

    for i in range(0, len(words), chunk_words):
        chunk = ' '.join(words[i:i + chunk_words])
        is_last = (i + chunk_words) >= len(words)
        # Add trailing space for non-final chunks so TTS doesn't clip words
        if not is_last:
            chunk += ' '
        frames.append(build_response_frame(
            response_id=rid,
            content=chunk,
            content_complete=is_last,
            end_call=False,
        ))

    # Edge case: empty response
    if not frames:
        frames.append(build_response_frame(
            response_id=rid,
            content="I'm sorry, I don't have that information right now.",
            content_complete=True,
            end_call=False,
        ))

    return frames
