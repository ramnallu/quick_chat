"""Voice-friendly response formatting utilities.

Converts chat-style RAG responses (markdown, bullet lists, links) into
natural spoken language suitable for text-to-speech output via Retell AI.
"""

import re


# Maximum word count for a voice response (~30 seconds of speech)
MAX_VOICE_WORDS = 75


def strip_markdown(text: str) -> str:
    """Remove markdown formatting that doesn't translate to speech."""
    # Remove bold/italic markers
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # Remove markdown links, keep the label
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # Remove inline code backticks
    text = re.sub(r'`(.+?)`', r'\1', text)

    # Remove heading markers
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    return text.strip()


def convert_lists_to_prose(text: str) -> str:
    """Convert numbered/bulleted lists into comma-separated spoken phrases."""
    lines = text.split('\n')
    result_lines = []
    list_items = []

    def flush_list():
        if not list_items:
            return
        if len(list_items) == 1:
            result_lines.append(list_items[0])
        elif len(list_items) == 2:
            result_lines.append(f"{list_items[0]} and {list_items[1]}")
        else:
            joined = ', '.join(list_items[:-1]) + f', and {list_items[-1]}'
            result_lines.append(joined)
        list_items.clear()

    for line in lines:
        stripped = line.strip()
        # Match numbered lists (1. item) or bulleted lists (- item, * item)
        list_match = re.match(r'^(?:\d+[\.\)]\s*|[-*+]\s+)(.+)', stripped)
        if list_match:
            item = list_match.group(1).strip()
            # Remove trailing periods from list items for cleaner joining
            item = item.rstrip('.')
            if item:
                list_items.append(item)
        else:
            flush_list()
            if stripped:
                result_lines.append(stripped)

    flush_list()
    return '. '.join(result_lines)


def truncate_for_voice(text: str, max_words: int = MAX_VOICE_WORDS) -> str:
    """Truncate response to fit within voice time budget.

    Tries to cut at sentence boundaries. If the full text fits, returns it
    unchanged.
    """
    words = text.split()
    if len(words) <= max_words:
        return text

    # Cut at the max word boundary then back-track to the last sentence end
    truncated = ' '.join(words[:max_words])
    last_period = truncated.rfind('.')
    last_question = truncated.rfind('?')
    last_exclaim = truncated.rfind('!')
    cut_point = max(last_period, last_question, last_exclaim)

    if cut_point > len(truncated) // 3:
        truncated = truncated[:cut_point + 1]
    else:
        truncated = truncated.rstrip() + '.'

    return truncated


def clean_for_speech(text: str) -> str:
    """Normalize text for cleaner TTS output."""
    # Expand common abbreviations
    replacements = {
        ' & ': ' and ',
        ' w/ ': ' with ',
        ' w/o ': ' without ',
        ' vs ': ' versus ',
        ' approx ': ' approximately ',
        ' approx. ': ' approximately ',
        ' info ': ' information ',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove stray special characters that TTS may mispronounce
    text = re.sub(r'[•·|~^]', '', text)

    return text.strip()


def format_for_voice(raw_response: str) -> str:
    """Full pipeline: convert a chat RAG response into voice-friendly text.

    Steps:
        1. Strip markdown formatting
        2. Convert lists to prose
        3. Clean for speech
        4. Truncate to voice time budget
    """
    text = strip_markdown(raw_response)
    text = convert_lists_to_prose(text)
    text = clean_for_speech(text)
    text = truncate_for_voice(text)
    return text
