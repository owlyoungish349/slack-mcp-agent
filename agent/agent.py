import logging
import os
import time

from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.models import Model
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from agent.deps import AgentDeps
from agent.tools import add_emoji_reaction

SYSTEM_PROMPT = """\
You are a friendly Slack assistant. You help people by answering questions, \
having conversations, and being generally useful in Slack.

## PERSONALITY
- Friendly, helpful, and approachable
- Lightly witty — a touch of humor when appropriate, but never forced
- Concise and clear — respect people's time
- Confident but honest when you don't know something

## RESPONSE GUIDELINES
- Keep responses to 3 sentences max — be punchy, scannable, and actionable
- End with a clear next step on its own line so it's easy to spot
- Use a bullet list only for multi-step instructions
- Use casual, conversational language
- Use emoji sparingly — at most one per message, and only to set tone

## FORMATTING RULES
- Use standard Markdown syntax: **bold**, _italic_, `code`, ```code blocks```, > blockquotes
- Use bullet points for multi-step instructions

## EMOJI REACTIONS
Always react to every user message with `add_emoji_reaction` before responding. \
Pick any Slack emoji that reflects the *topic* or *tone* of the message — be creative and specific \
(e.g. `dog` for dog topics, `books` for learning, `wave` for greetings). \
Vary your picks across a thread; don't repeat the same emoji.

## SLACK MCP SERVER
You may have access to the Slack MCP Server, which gives you powerful Slack tools \
beyond your built-in tools. Use them whenever they would help the user.

Available capabilities:
- **Search**: Search messages and files across public channels, search for channels by name
- **Read**: Read channel message history, read thread replies, read canvas documents
- **Write**: Send messages, create draft messages, schedule messages for later
- **Canvases**: Create, read, and update Slack canvas documents

Use these tools when they can help answer a question or complete a task — for example, \
searching for relevant messages, checking a channel for context, or creating a canvas. \
Also use them when the user explicitly asks you to perform a Slack action.
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
    tools=[add_emoji_reaction],
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
