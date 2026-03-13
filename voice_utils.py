"""Voice-friendly response formatting utilities.

Converts RAG pipeline responses into concise, warm, phone-optimized text
using LLM-based consolidation instead of simple truncation.
"""

import logging
import os
import re

logger = logging.getLogger("voice_utils")

MAX_VOICE_WORDS = 80

# ---------------------------------------------------------------------------
# LLM-based voice consolidation prompt
# ---------------------------------------------------------------------------

VOICE_SYSTEM_PROMPT = """You are a friendly, warm phone agent for a local business. 
Convert the following written response into a natural phone conversation reply.

Rules:
- Be positive, polite, and engaging — like a real person who loves their job
- Use conversational language — say "we've got" instead of "the menu features"
- Keep it concise: 2-4 sentences max, around 50-70 words
- DO NOT list every single item — pick the top highlights and say "and more"
- DO NOT use numbering, bullet points, or markdown
- DO NOT mention prices unless the caller specifically asked about pricing
- DO NOT say "according to our records" or "based on our data"
- End with something inviting like "Would you like to know more about any of these?" or "Can I help you with anything else?"
- Sound natural when read aloud — avoid long compound sentences
- If the original response says information is not available, be honest but helpful"""

VOICE_USER_TEMPLATE = """Caller asked: "{question}"

Written response to consolidate for phone:
{answer}

Rewrite this as a warm, natural phone reply:"""


def format_for_voice(text: str, question: str = "", max_words: int = MAX_VOICE_WORDS) -> str:
    """Convert a text response into voice-friendly format.

    Tries LLM-based consolidation first for natural-sounding speech.
    Falls back to rule-based formatting if LLM is unavailable.
    """
    # Try LLM consolidation first
    if question:
        try:
            consolidated = _llm_consolidate(text, question)
            if consolidated:
                return consolidated.strip()
        except Exception as e:
            logger.warning("LLM consolidation failed, falling back to rules: %s", e)

    # Fallback: rule-based formatting
    return _rule_based_format(text, max_words)


def _llm_consolidate(text: str, question: str) -> str | None:
    """Use the same LLM provider as the RAG pipeline to consolidate."""
    provider = os.environ.get("LLM_PROVIDER", "ollama").lower()

    prompt = VOICE_USER_TEMPLATE.format(question=question, answer=text[:1500])

    if provider == "groq":
        return _consolidate_groq(prompt)
    else:
        return _consolidate_ollama(prompt)


def _consolidate_groq(prompt: str) -> str | None:
    """Consolidate using Groq."""
    from langchain_groq import ChatGroq

    api_key = os.environ.get("GROQ_API_KEY", "")
    model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        return None

    llm = ChatGroq(api_key=api_key, model_name=model, temperature=0.3)
    messages = [
        ("system", VOICE_SYSTEM_PROMPT),
        ("human", prompt),
    ]
    response = llm.invoke(messages)
    result = response.content if hasattr(response, "content") else str(response)

    # Safety check: strip any markdown that leaked through
    result = _strip_markdown(result)
    return result.strip()


def _consolidate_ollama(prompt: str) -> str | None:
    """Consolidate using Ollama."""
    from langchain_ollama import OllamaLLM

    url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.environ.get("OLLAMA_MODEL", "llama3.2")

    llm = OllamaLLM(base_url=url, model=model, temperature=0.3)
    full_prompt = f"{VOICE_SYSTEM_PROMPT}\n\n{prompt}"
    result = llm.invoke(full_prompt)

    result = _strip_markdown(result)
    return result.strip()


# ---------------------------------------------------------------------------
# Rule-based fallback (improved from original)
# ---------------------------------------------------------------------------

def _rule_based_format(text: str, max_words: int = MAX_VOICE_WORDS) -> str:
    """Fallback formatter: strips markdown, converts lists, truncates."""
    text = _strip_markdown(text)
    text = _lists_to_prose(text)
    text = _normalize_whitespace(text)
    text = _add_warmth(text)
    text = _truncate(text, max_words)
    return text.strip()


def _add_warmth(text: str) -> str:
    """Add a friendly closing if the response doesn't already have one."""
    friendly_closings = [
        "would you like", "can i help", "anything else",
        "let me know", "happy to help", "glad to",
    ]
    has_closing = any(c in text.lower() for c in friendly_closings)

    if not has_closing and len(text.split()) > 10:
        text = text.rstrip(".")
        text += ". Would you like to know more?"

    return text


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _strip_markdown(text: str) -> str:
    """Remove markdown formatting."""
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Remove numbered list prefixes like "1. " at start of lines
    text = re.sub(r"^\d+\.\s+", "", text, flags=re.MULTILINE)
    return text


def _lists_to_prose(text: str) -> str:
    """Turn bullet/numbered list items into flowing prose."""
    lines = text.split("\n")
    result: list[str] = []
    list_items: list[str] = []

    for line in lines:
        stripped = line.strip()
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
    # For long lists, highlight first few and summarize
    if len(items) > 5:
        highlighted = ", ".join(items[:4])
        return f"{highlighted}, and several more options."
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

    last_period = truncated.rfind(".")
    last_question = truncated.rfind("?")
    last_excl = truncated.rfind("!")
    boundary = max(last_period, last_question, last_excl)

    if boundary > len(truncated) // 2:
        return truncated[: boundary + 1]

    return truncated.rstrip(".,;:!? ") + "."
