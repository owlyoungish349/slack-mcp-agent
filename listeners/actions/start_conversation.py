"""Open a welcoming Threshold DM from the App Home launch button."""

from logging import Logger

from slack_bolt import Ack
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from listeners.views.threshold_blocks import build_welcome_blocks


def handle_start_conversation(
    ack: Ack, body: dict, client: WebClient, logger: Logger
) -> None:
    """Send a fresh language picker when a member starts from App Home."""
    ack()

    user_id = body["user"]["id"]
    try:
        user = client.users_info(user=user_id)["user"]
        profile = user.get("profile", {})
        user_name = profile.get("display_name") or user.get("real_name") or "friend"
        dm_channel = client.conversations_open(users=user_id)["channel"]["id"]
        client.chat_postMessage(
            channel=dm_channel,
            text=f"Welcome, {user_name}! Choose your language to get started.",
            blocks=build_welcome_blocks(user_name),
        )
    except SlackApiError as exc:
        logger.exception(
            "Could not start a Threshold conversation for %s: %s", user_id, exc
        )
