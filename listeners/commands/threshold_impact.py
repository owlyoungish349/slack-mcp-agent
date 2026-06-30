"""Flow F — /threshold-impact

Renders a Block Kit impact dashboard showing key Threshold metrics:
members welcomed, languages served, groups matched, intros posted,
digests sent, referrals needed (target: 0), and avg. time to first connection.
"""

from logging import Logger

from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from store import user_store
from listeners.views.threshold_blocks import build_impact_blocks


def handle_threshold_impact(
    ack: Ack,
    body: dict,
    client: WebClient,
    context: BoltContext,
    logger: Logger,
) -> None:
    ack()

    channel_id = body.get("channel_id") or body.get("channel", {}).get("id")
    user_id = body["user_id"]

    try:
        summary = user_store.get_impact_summary()
        blocks = build_impact_blocks(summary)

        # Post as an ephemeral message so only the caller sees it (or in-channel if preferred)
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            text="📊 Threshold Impact Dashboard",
            blocks=blocks,
        )
        logger.info("Impact dashboard shown to %s", user_id)

    except SlackApiError as e:
        logger.exception("Failed to show impact dashboard: %s", e)
