from pydantic_ai import RunContext

from agent.deps import AgentDeps
from store import user_store

_VALID_EVENTS = {"welcomed", "language_set", "matched", "intro_made", "digest_sent"}


async def log_impact_event(
    ctx: RunContext[AgentDeps],
    event_type: str,
    user_id: str | None = None,
    language: str | None = None,
    detail: str | None = None,
) -> str:
    """Log a Threshold impact event to the persistent store.

    Call this whenever a meaningful action occurs so the /threshold-impact
    dashboard stays up-to-date.

    Args:
        ctx: The run context with dependencies.
        event_type: One of: welcomed, language_set, matched, intro_made, digest_sent.
        user_id: The Slack user ID this event relates to (optional).
        language: ISO 639-1 language code (optional).
        detail: Free-text description stored as metadata (optional).
    """
    if event_type not in _VALID_EVENTS:
        return f"Unknown event_type '{event_type}'. Valid values: {', '.join(sorted(_VALID_EVENTS))}"
    metadata = {"detail": detail} if detail else None
    user_store.log_event(event_type, user_id, language, metadata)
    return f"Logged impact event: {event_type}" + (f" for {user_id}" if user_id else "")
