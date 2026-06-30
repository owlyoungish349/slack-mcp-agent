import logging
import os
import time

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from agent.deps import AgentDeps
from agent.tools import add_emoji_reaction, get_user_language, log_impact_event, set_user_language

SYSTEM_PROMPT = """\
You are *Threshold* — a multilingual belonging agent for Cornerstone Community Church. \
Your mission: help newcomers, especially those with limited English, discover life groups, \
classes, volunteering, and community — without needing a referral or knowing the right person.

## LANGUAGE
- ALWAYS call `get_user_language` first to discover the user's preference before responding.
- Respond in the user's preferred language once you know it.
- If no preference is stored, ask which language they prefer (offer: English, Spanish, Arabic, Polish, Portuguese, Romanian).
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
2. **Use the Slack MCP Server to search `#groups-directory`** for matching entries. \
   Search query: the member's stated interest (e.g. "english conversation", "café volunteer", "families children").
3. Read the search results and identify the top 2–3 matching groups.
4. Present each match clearly in the member's language:
   - Group name, schedule, description, languages supported, contact person, and channel.
5. Ask: "Would you like me to introduce you to one of these groups?"
6. If they say yes:
   - **Use MCP to post an intro message in the group's channel**, @-mentioning both the group contact and the newcomer.
   - The intro should be warm and in English (so the contact can read it), with the newcomer's name and interest.
   - Log `log_impact_event(event_type='intro_made', ...)`.
7. Log `log_impact_event(event_type='matched', ...)` when you present the matches.

CRITICAL: The group search and intro post MUST use the Slack MCP Server tools — not a local lookup.

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
"""

logger = logging.getLogger(__name__)

_cached_model: str | Model | None = None

# Pydantic AI's GoogleProvider reads GOOGLE_API_KEY; older versions read
# GEMINI_API_KEY. Both are set in .env to be safe across versions.
GEMINI_MODEL_NAME = "gemini-2.5-flash"


def get_model() -> str | Model:
    """Select the AI model based on available API keys.

    Prefers Google Gemini (this project's baseline LLM), then falls back to
    Anthropic, then OpenAI if their keys are set instead.
    """
    global _cached_model
    if _cached_model is not None:
        return _cached_model

    google_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if google_key:
        provider = GoogleProvider(api_key=google_key)
        _cached_model = GoogleModel(GEMINI_MODEL_NAME, provider=provider)
    elif os.environ.get("ANTHROPIC_API_KEY"):
        _cached_model = "anthropic:claude-sonnet-4-6"
    elif os.environ.get("OPENAI_API_KEY"):
        _cached_model = "openai:gpt-4.1-mini"
    else:
        raise RuntimeError(
            "No AI provider configured. "
            "Set GOOGLE_API_KEY (or GEMINI_API_KEY), ANTHROPIC_API_KEY, or "
            "OPENAI_API_KEY in your environment."
        )
    return _cached_model


def _is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc)
    return (
        "429" in message
        or "RESOURCE_EXHAUSTED" in message
        or "rate limit" in message.lower()
    )


def _run_with_backoff(fn, *, max_retries: int = 3, base_delay: float = 1.0):
    """Retry on Gemini free-tier 429/RESOURCE_EXHAUSTED with exponential backoff."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt == max_retries:
                raise
            delay = base_delay * (2**attempt)
            logger.warning(
                "Gemini rate limited (attempt %d/%d), retrying in %.1fs",
                attempt + 1,
                max_retries + 1,
                delay,
            )
            time.sleep(delay)


SLACK_MCP_URL = "https://mcp.slack.com/mcp"

agent = Agent(
    deps_type=AgentDeps,
    system_prompt=SYSTEM_PROMPT,
    tools=[add_emoji_reaction, get_user_language, set_user_language, log_impact_event],
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
