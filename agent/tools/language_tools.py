from pydantic_ai import RunContext

from agent.deps import AgentDeps
from store import user_store


async def get_user_language(ctx: RunContext[AgentDeps], user_id: str) -> str:
    """Get a user's stored language preference.

    Returns a string like "Spanish (es)" or "English (en)" if no preference is stored.

    Args:
        ctx: The run context with dependencies.
        user_id: The Slack user ID (e.g. 'U012AB3CD').
    """
    lang, name = user_store.get_language(user_id)
    return f"{name} ({lang})"


async def set_user_language(
    ctx: RunContext[AgentDeps],
    user_id: str,
    language_code: str,
    language_name: str,
) -> str:
    """Store a user's preferred language and log the language_set event.

    Args:
        ctx: The run context with dependencies.
        user_id: The Slack user ID.
        language_code: ISO 639-1 code, e.g. 'es', 'ar', 'pl'.
        language_name: Human-readable name, e.g. 'Spanish', 'Arabic', 'Polish'.
    """
    user_store.set_language(user_id, language_code, language_name)
    user_store.log_event("language_set", user_id, language_code)
    return f"Language preference saved: {language_name} ({language_code}) for user {user_id}"
