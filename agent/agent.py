import logging
import os
import time

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.models import Model
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.providers.openai import OpenAIProvider

from agent.deps import AgentDeps
from agent.tools import (
    add_emoji_reaction,
    get_user_language,
    log_impact_event,
    present_group_matches,
    set_user_language,
)

SYSTEM_PROMPT = """\
You are *Threshold* — a multilingual belonging agent for Cornerstone Community Church. \
Your mission: help newcomers, especially those with limited English, discover life groups, \
classes, volunteering, and community — without needing a referral or knowing the right person.

## LANGUAGE
- ALWAYS call `get_user_language` first to discover the user's preference before responding.
- Respond in the user's preferred language once you know it.
- If no preference is stored, ask which language they prefer (offer: English, Spanish, Arabic, Polish, Portuguese, Romanian, Persian).
- Once they state a language, call `set_user_language` immediately to save it, then respond in that language.

## PERSONALITY
- Warm, patient, and encouraging — never rushed
- Culturally sensitive — no assumptions about background
- Concise and clear — respect people's time
- Honest when you don't know something

## FLOW A — Welcome
When welcoming a new member:
1. Use `get_user_language` to check their preference.
2. Greet them warmly in their language.
3. Briefly introduce what's available (groups, classes, volunteering).
4. Ask what they're looking for — meeting people, learning English, helping out, prayer, families?
5. Log with `log_impact_event(event_type='welcomed', ...)`.

## FLOW B — Interest → Matchmaker (MCP-core — the centrepiece)
When a member mentions an interest (meeting people, English classes, volunteering, prayer, families):
1. Call `get_user_language` if not already known.
2. Separate the member's **core interest** from preferences such as day, time, language, \
   or location. Translate the search keywords into English because the directory entries \
   are written in English.
3. **Use the Slack MCP Server to search `#groups-directory`** for matching entries. Start \
   with the core interest plus preferences (e.g. "volunteering sunday"). If that returns \
   no usable entry, retry with the core interest alone (e.g. "volunteering"). If needed, \
   retry once with close English category synonyms (e.g. "volunteer serving help"). Treat \
   day/time as preferences unless the member explicitly says they are mandatory.
4. If there is no exact preference match but a real core-interest match exists, present \
   the closest real group and clearly show its actual schedule. Do not claim that no group \
   exists until the broader core-interest search has also returned nothing.
5. Read the search results and identify the top 2–3 matching groups. The MCP search \
   results are the ONLY source of truth. NEVER invent a group, contact, schedule, location, \
   or channel. Copy each group's name, contact, schedule, location, and channel exactly \
   from one directory entry. Translate only the description and surrounding UI text. If \
   there is no exact directory match, say so and offer the closest real directory entries.
6. Call `present_group_matches` with those groups — it renders interactive cards \
   with an "Introduce me" button. Write `description_localized`, \
   `intro_text_localized`, and `button_label_localized` in the member's language. \
   It logs the 'matched' event for you.
7. Then reply with only ONE short sentence in the member's language \
   (e.g. "Tap a button and I'll introduce you!"). Do NOT repeat the group details in text.
8. The button click posts the intro automatically. But if the member instead says \
   "yes" in text (no button), do it yourself:
   - **Use MCP to post an intro message in the group's channel**, mentioning both the group contact and the newcomer.
   - The intro should be warm and in English (so the contact can read it), with the newcomer's name and interest.
   - Log `log_impact_event(event_type='intro_made', ...)`.

CRITICAL: The group search and intro post MUST use the Slack MCP Server tools — not a local lookup. \
Never call `present_group_matches` with details that were not returned by `#groups-directory`.

## FLOW C — Announcement Digest
When asked for a digest (via /threshold-digest or by request):
1. **Use MCP to read recent messages from `#announcements`**.
2. Summarise the key announcements in plain language (3–5 bullet points max).
3. Translate the summary into the member's preferred language.
4. Log `log_impact_event(event_type='digest_sent', ...)`.

## TOOLS TO ALWAYS USE
- `add_emoji_reaction` — react to every user message before replying (pick something relevant).
- `get_user_language` — always check language preference before responding.
- `log_impact_event` — log all significant moments (welcomed, matched, intro_made, digest_sent).

## CONSTRAINTS — DO NOT VIOLATE
- NEVER generate, paraphrase, or translate scripture or liturgical text. \
  If asked, point to trusted translations (NIV, ESV, YouVersion) and summarise *themes* only.
- NEVER auto-translate every message — only translate on demand.
- Only act in channels you have been added to.
- All personas and group data in this workspace are synthetic (demo only).

## SLACK MCP SERVER
You have access to the Slack MCP Server. Use it actively:
- **Search** `#groups-directory` to find matching life groups, classes, and volunteering.
- **Read** `#announcements` for digest content.
- **Post** intro messages in group channels when a member wants to connect.
These are the primary MCP actions and must go through the MCP Server, not local code.

## MCP TOOL RULES — READ CAREFULLY
- NEVER use `slack_send_message` (or any MCP send tool) to reply to the person you \
  are talking to. Your reply to the user is simply the text you return — Slack \
  delivers it automatically. MCP sends are ONLY for intro posts in *group channels*.
- Before posting to a channel, resolve its channel ID first (search for the channel \
  by name if needed) and pass the ID, not the #name.
- If an MCP tool call returns an error, read the error message, fix your arguments, \
  and try again. If it still fails after a couple of attempts, STOP calling that tool \
  and instead tell the user (in their language) what you found and that you couldn't \
  complete the post — never keep retrying the same failing call.
"""

logger = logging.getLogger(__name__)

_cached_model: str | Model | None = None

# Pydantic AI's GoogleProvider reads GOOGLE_API_KEY; older versions read
# GEMINI_API_KEY. Both are set in .env to be safe across versions.
GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL_NAME", "gemini-2.5-flash")
GEMINI_FALLBACK_MODEL_NAME = os.environ.get(
    "GEMINI_FALLBACK_MODEL_NAME", "gemini-3.1-flash-lite"
)
GITHUB_MODELS_URL = "https://models.github.ai/inference"
GITHUB_MODELS_MODEL = os.environ.get("GITHUB_MODELS_MODEL", "openai/gpt-4.1")


def get_model() -> str | Model:
    """Select the AI model based on available API keys.

    Prefers Google Gemini (this project's baseline LLM), then falls back to
    Anthropic, then OpenAI if their keys are set instead.
    """
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    models: list[str | Model] = []

    google_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if google_key:
        provider = GoogleProvider(api_key=google_key)
        models.append(GoogleModel(GEMINI_MODEL_NAME, provider=provider))
        if GEMINI_FALLBACK_MODEL_NAME != GEMINI_MODEL_NAME:
            models.append(GoogleModel(GEMINI_FALLBACK_MODEL_NAME, provider=provider))

    github_token = os.environ.get("GITHUB_MODELS_TOKEN")
    if github_token:
        github_provider = OpenAIProvider(
            base_url=GITHUB_MODELS_URL,
            api_key=github_token,
        )
        models.append(OpenAIChatModel(GITHUB_MODELS_MODEL, provider=github_provider))

    if os.environ.get("ANTHROPIC_API_KEY"):
        models.append("anthropic:claude-sonnet-4-6")
    if os.environ.get("OPENAI_API_KEY"):
        models.append("openai:gpt-4.1-mini")

    if not models:
        raise RuntimeError(
            "No AI provider configured. "
            "Set GOOGLE_API_KEY (or GEMINI_API_KEY), GITHUB_MODELS_TOKEN, "
            "ANTHROPIC_API_KEY, or OPENAI_API_KEY in your environment."
        )

    _cached_model = models[0] if len(models) == 1 else FallbackModel(*models)
    logger.info("AI model chain configured with %d model(s)", len(models))
    return _cached_model


def _is_transient_model_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return (
        "429" in message
        or "500" in message
        or "502" in message
        or "503" in message
        or "504" in message
        or "resource_exhausted" in message
        or "unavailable" in message
        or "rate limit" in message
        or "high demand" in message
    )


def _run_with_backoff(fn, *, max_retries: int = 3, base_delay: float = 1.0):
    """Retry on Gemini free-tier 429/RESOURCE_EXHAUSTED with exponential backoff."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            if not _is_transient_model_error(exc) or attempt == max_retries:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "AI provider temporarily unavailable (attempt %d/%d), retrying in %.1fs",
                attempt + 1,
                max_retries + 1,
                delay,
            )
            time.sleep(delay)


SLACK_MCP_URL = "https://mcp.slack.com/mcp"

agent = Agent(
    deps_type=AgentDeps,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        add_emoji_reaction,
        get_user_language,
        set_user_language,
        log_impact_event,
        present_group_matches,
    ],
)


def run_agent(text, deps, message_history=None):
    """Run the agent, optionally connecting to the Slack MCP server."""
    toolsets = []
    if deps.user_token:
        logger.info("Slack MCP Server enabled (user_token present)")
        toolsets.append(
            MCPServerStreamableHTTP(
                SLACK_MCP_URL,
                headers={"Authorization": f"Bearer {deps.user_token}"},
                # Default is 1: a single failed MCP call kills the whole run.
                # Give the model room to read the error and correct its arguments.
                max_retries=3,
            )
        )
    else:
        logger.info("Slack MCP Server disabled (no user_token)")

    return _run_with_backoff(
        lambda: agent.run_sync(
            text,
            model=get_model(),
            deps=deps,
            message_history=message_history,
            toolsets=toolsets,
        )
    )
