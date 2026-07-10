"""On-demand translation using Threshold's resilient model chain."""

from pydantic_ai import Agent

from agent.agent import _run_with_backoff, get_model

_translator = Agent(
    system_prompt=(
        "You are a precise translation assistant for a welcoming church community. "
        "Return only the requested translation, preserving names, links, Slack mentions, "
        "formatting, and the original meaning. Do not add commentary. "
        "Do not translate scripture or liturgical text; instead, briefly say that you "
        "cannot translate it and point to trusted translations."
    )
)


def translate_text(text: str, target_language: str) -> str:
    """Translate text on demand using the configured model fallback chain."""
    prompt = (
        f"Translate the text between <message> tags into {target_language}.\n"
        "<message>\n"
        f"{text}\n"
        "</message>"
    )
    result = _run_with_backoff(lambda: _translator.run_sync(prompt, model=get_model()))
    return result.output.strip()
