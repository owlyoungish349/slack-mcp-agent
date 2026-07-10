from logging import Logger

from slack_bolt.context.set_suggested_prompts import SetSuggestedPrompts

SUGGESTED_PROMPTS = [
    {
        "title": "Find a group",
        "message": "I'd like to meet some people and find a group to join.",
    },
    {
        "title": "Volunteer",
        "message": "I'd love to help out — what volunteering opportunities are there?",
    },
    {
        "title": "English classes",
        "message": "Are there any English conversation or language classes?",
    },
    {
        "title": "This week's news",
        "message": "What's happening at church this week?",
    },
]


def handle_assistant_thread_started(
    set_suggested_prompts: SetSuggestedPrompts, logger: Logger
):
    """Handle assistant thread started events by setting suggested prompts."""
    try:
        set_suggested_prompts(
            prompts=SUGGESTED_PROMPTS,
            title="Welcome — how can I help you get connected?",
        )
    except Exception as e:
        logger.exception(f"Failed to handle assistant thread started: {e}")
