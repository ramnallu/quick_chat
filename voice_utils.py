"""Voice-friendly response formatting utilities.

Converts RAG pipeline responses into concise, speech-optimized text
suitable for TTS playback over phone calls.
"""

import re

MAX_VOICE_WORDS = 75


def format_for_voice(text: str, max_words: int = MAX_VOICE_WORDS) -> str:
    """Convert a text response into voice-friendly format.

    - Strips markdown formatting (bold, italic, links, headers, code blocks)
    - Converts bullet/numbered lists into flowing prose
    - Normalizes whitespace
    - Truncates to *max_words* on a sentence boundary
    """
    text = _strip_markdown(text)
    text = _lists_to_prose(text)
    text = _normalize_whitespace(text)
    text = _truncate(text, max_words)
    return text.strip()


# -- internal helpers --------------------------------------------------------

def _strip_markdown(text: str) -> str:
    # Code blocks (fenced and inline)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)

    # Headers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Bold / italic
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)

    # Links  [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Images
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)

    # Horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    return text


def _lists_to_prose(text: str) -> str:
    """Turn bullet / numbered list items into comma-separated prose."""
    lines = text.split("\n")
    result: list[str] = []
    list_items: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Match "- item", "* item", "1. item", "2) item"
        m = re.match(r"^(?:[-*]|\d+[.)]) \s*(.*)", stripped)
        if m:
            item = m.group(1).rstrip(".")
            if item:
                list_items.append(item)
        else:
            if list_items:
                result.append(_join_items(list_items))
                list_items = []
            if stripped:
                result.append(stripped)

    if list_items:
        result.append(_join_items(list_items))

    return " ".join(result)


def _join_items(items: list[str]) -> str:
    if len(items) == 1:
        return items[0] + "."
    if len(items) == 2:
        return f"{items[0]} and {items[1]}."
    return ", ".join(items[:-1]) + f", and {items[-1]}."


def _normalize_whitespace(text: str) -> str:
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _truncate(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text

    truncated = " ".join(words[:max_words])

    # Try to cut on a sentence boundary
    last_period = truncated.rfind(".")
    last_question = truncated.rfind("?")
    last_excl = truncated.rfind("!")
    boundary = max(last_period, last_question, last_excl)

    if boundary > len(truncated) // 2:
        return truncated[: boundary + 1]

    return truncated.rstrip(".,;:!? ") + "."
