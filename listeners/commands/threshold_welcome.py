"""Flow A (manual trigger) — /threshold-welcome @user

Lets operators or admins manually kick off the welcome flow for a specific
member. Useful for demos and for members who joined before the bot was added.

Usage: /threshold-welcome @username
"""

import re
from logging import Logger

from slack_bolt import Ack, BoltContext, Respond
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from store import user_store
from listeners.views.threshold_blocks import build_welcome_blocks


def handle_threshold_welcome(
    ack: Ack,
    body: dict,
    client: WebClient,
    context: BoltContext,
    respond: Respond,
    logger: Logger,
) -> None:
    ack()

    text = (body.get("text") or "").strip()
    # Extract user ID from @-mention like <@U012AB3CD> or <@U012AB3CD|username>
    match = re.search(r"<@([A-Z0-9]+)(?:\|[^>]+)?>", text)
    if not match:
        respond(
            text="Usage: `/threshold-welcome @username`\nTag the user you want to welcome.",
            response_type="ephemeral",
        )
        return

    target_user_id = match.group(1)

    try:
        info = client.users_info(user=target_user_id)
        if info["user"].get("is_bot"):
            respond(
                text=f"<@{target_user_id}> is a bot — no welcome needed!",
                response_type="ephemeral",
            )
            return
        user_name = (
            info["user"].get("profile", {}).get("display_name")
            or info["user"].get("real_name")
            or "friend"
        )
    except SlackApiError as e:
        respond(
            text=f"Could not look up user: `{e.response['error']}`",
            response_type="ephemeral",
        )
        return

    try:
        dm = client.conversations_open(users=target_user_id)
        dm_channel = dm["channel"]["id"]

        client.chat_postMessage(
            channel=dm_channel,
            text=f"Welcome to Cornerstone Community Church, {user_name}! I'm Threshold.",
            blocks=build_welcome_blocks(user_name),
        )

        # Log welcomed event (idempotent — log even if already welcomed, for the demo)
        user_store.log_event("welcomed", target_user_id)

        respond(
            text=f"✅ Welcome DM sent to <@{target_user_id}>.",
            response_type="ephemeral",
        )
        logger.info("Manual welcome sent to %s (%s)", user_name, target_user_id)

    except SlackApiError as e:
        logger.exception("Failed to send welcome DM to %s: %s", target_user_id, e)
        respond(
            text=f"Could not send DM: `{e.response['error']}`",
            response_type="ephemeral",
        )
