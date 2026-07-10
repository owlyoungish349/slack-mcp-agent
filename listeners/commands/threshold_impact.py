"""Flow F — /threshold-impact

Renders a Block Kit impact dashboard showing key Threshold metrics:
members welcomed, languages served, groups matched, intros posted,
digests sent, referrals needed (target: 0), and avg. time to first connection.
"""

from logging import Logger

from slack_bolt import Ack, Respond

from store import user_store
from listeners.views.threshold_blocks import build_impact_blocks


def handle_threshold_impact(
    ack: Ack,
    respond: Respond,
    logger: Logger,
) -> None:
    ack()

    try:
        summary = user_store.get_impact_summary()
        blocks = build_impact_blocks(summary)

        respond(
            text="📊 Threshold Impact Dashboard",
            blocks=blocks,
            response_type="ephemeral",
        )
        logger.info("Impact dashboard shown")

    except Exception as e:
        logger.exception("Failed to show impact dashboard: %s", e)
        respond(
            text="⚠️ I couldn't load the impact dashboard just now.",
            response_type="ephemeral",
        )
