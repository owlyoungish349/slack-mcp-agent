"""Flow A — welcome trigger.

Fires whenever any member joins a channel. If the user has not yet been
welcomed by Threshold, the bot opens a DM and sends the language-picker card.
"""

from logging import Logger

from slack_bolt import BoltContext
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from store import user_store
from listeners.views.threshold_blocks import build_welcome_blocks


def handle_member_joined_channel(
    client: WebClient,
    context: BoltContext,
    event: dict,
    logger: Logger,
) -> None:
    user_id = event.get("user")
    if not user_id:
        return

    # Ignore bot joins
    try:
        info = client.users_info(user=user_id)
        if info["user"].get("is_bot"):
            return
        user_name = (
            info["user"].get("profile", {}).get("display_name")
            or info["user"].get("real_name")
            or "friend"
        )
    except SlackApiError as e:
        logger.warning("Could not fetch user info for %s: %s", user_id, e)
        user_name = "friend"

    # Only welcome each user once, even if they join multiple channels
    if user_store.was_welcomed(user_id):
        return

    try:
        dm = client.conversations_open(users=user_id)
        dm_channel = dm["channel"]["id"]

        client.chat_postMessage(
            channel=dm_channel,
            text=f"Welcome to Cornerstone Community Church, {user_name}! I'm Threshold — let me help you get connected.",
            blocks=build_welcome_blocks(user_name),
        )

        user_store.log_event("welcomed", user_id)
        logger.info("Sent welcome DM to %s (%s)", user_name, user_id)

    except SlackApiError as e:
        logger.exception("Failed to send welcome DM to %s: %s", user_id, e)
