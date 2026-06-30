"""Flow C — /threshold-digest

Reads recent #announcements via the Slack MCP Server (through the agent),
translates the digest into each opted-in member's preferred language, and
DMs it to them.

If no opted-in members exist yet, it sends a preview to the command caller.
"""

import os
from logging import Logger

from slack_bolt import Ack, BoltContext, Respond
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from agent import AgentDeps, run_agent
from store import user_store
from listeners.utils import get_user_token
from listeners.views.threshold_blocks import build_digest_header_block


_DIGEST_PROMPT = """\
Please read the recent messages from the #announcements channel using the Slack MCP \
search or conversations tools. Then produce a plain-language digest with 3–5 bullet \
points covering the key announcements. Keep it warm and accessible.

Respond in {language_name}. After producing the digest, log an impact event: \
log_impact_event(event_type='digest_sent', user_id='{user_id}', language='{lang_code}').

Do not include scripture or liturgical content.
"""


def _send_digest_to_user(
    client: WebClient,
    user_id: str,
    lang_code: str,
    lang_name: str,
    user_token: str | None,
    logger: Logger,
) -> None:
    """Open a DM to user_id and send an AI-generated translated digest."""
    try:
        dm = client.conversations_open(users=user_id)
        dm_channel = dm["channel"]["id"]
    except SlackApiError as e:
        logger.warning("Could not open DM to %s: %s", user_id, e)
        return

    # Build deps with the channel as the DM channel so the agent can react
    deps = AgentDeps(
        client=client,
        user_id=user_id,
        channel_id=dm_channel,
        thread_ts="",   # not in a thread
        message_ts="",
        user_token=user_token,
    )

    prompt = _DIGEST_PROMPT.format(
        language_name=lang_name, user_id=user_id, lang_code=lang_code
    )

    try:
        result = run_agent(prompt, deps)
        digest_text = result.output

        header = build_digest_header_block(lang_name)
        client.chat_postMessage(
            channel=dm_channel,
            text=digest_text,
            blocks=[
                header,
                {"type": "divider"},
                {"type": "section", "text": {"type": "mrkdwn", "text": digest_text}},
            ],
        )
        logger.info("Digest sent to %s (%s)", user_id, lang_code)
    except Exception as e:
        logger.exception("Digest generation failed for %s: %s", user_id, e)


def handle_threshold_digest(
    ack: Ack,
    body: dict,
    client: WebClient,
    context: BoltContext,
    respond: Respond,
    logger: Logger,
) -> None:
    ack()

    caller_id = body["user_id"]
    user_token = get_user_token(context)

    if not user_token:
        respond(
            text=(
                "⚠️ No user token available for MCP. "
                "Set `SLACK_USER_TOKEN` in your environment so the digest can read #announcements."
            ),
            response_type="ephemeral",
        )
        return

    opted_in = user_store.get_opted_in_users()

    # Always include the caller for a self-preview even if no one else is opted in
    targets: list[str] = list(dict.fromkeys([caller_id] + opted_in))

    respond(
        text=f"⏳ Generating digest for {len(targets)} member(s)…",
        response_type="ephemeral",
    )

    for uid in targets:
        lang_code, lang_name = user_store.get_language(uid)
        _send_digest_to_user(client, uid, lang_code, lang_name, user_token, logger)

    respond(
        text=f"✅ Digest sent to {len(targets)} member(s).",
        response_type="ephemeral",
    )
