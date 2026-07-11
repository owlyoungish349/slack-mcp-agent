"""Flow B — present group matches as interactive Block Kit cards.

The agent finds groups via the Slack MCP Server (search of #groups-directory),
then calls `present_group_matches` to render them as cards with an
"Introduce me" button. The button click is handled by
listeners/actions/accept_intro.py, which asks the agent to post the intro
via MCP in the group's channel.
"""

import json
import logging

from pydantic import BaseModel, Field
from pydantic_ai import RunContext
from slack_sdk.errors import SlackApiError

from agent.deps import AgentDeps
from store import user_store

logger = logging.getLogger(__name__)


class GroupMatch(BaseModel):
    """One matched group from the #groups-directory search."""

    group_name: str = Field(description="Group name, e.g. 'Café Volunteering'")
    emoji: str = Field(
        default="🤝", description="One emoji that fits the group, e.g. '☕'"
    )
    schedule: str = Field(description="When it meets, e.g. 'Sundays 9:30–12:00'")
    location: str = Field(default="", description="Where it meets, e.g. 'Church Café'")
    languages: str = Field(
        default="", description="Languages supported, e.g. 'All languages welcome'"
    )
    contact: str = Field(
        description="Contact person's name/handle from the directory, e.g. 'james-t'"
    )
    channel: str = Field(
        description="The group's channel name WITHOUT '#', e.g. 'cafe-volunteers'"
    )
    description_localized: str = Field(
        description="1–2 sentence description of the group, written in the USER'S preferred language"
    )


def _public_channels(client) -> dict[str, str]:
    """Return public channel names mapped to IDs, following Slack pagination."""
    channels: dict[str, str] = {}
    cursor = None
    while True:
        response = client.conversations_list(
            types="public_channel",
            exclude_archived=True,
            limit=200,
            cursor=cursor,
        )
        for channel in response.get("channels", []):
            name = channel.get("name")
            channel_id = channel.get("id")
            if name and channel_id:
                channels[name] = channel_id
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            return channels


def _directory_messages(client, channel_id: str) -> list[str]:
    """Read the group directory records used to ground match cards."""
    messages: list[str] = []
    cursor = None
    while True:
        response = client.conversations_history(
            channel=channel_id,
            limit=200,
            cursor=cursor,
        )
        messages.extend(
            message.get("text", "").casefold()
            for message in response.get("messages", [])
        )
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            return messages


def _verified_matches(client, matches: list[GroupMatch]) -> list[GroupMatch]:
    """Keep only matches whose channel/contact pair exists in one directory record."""
    try:
        channels = _public_channels(client)
        directory_id = channels.get("groups-directory")
        if not directory_id:
            logger.error("Cannot validate matches: #groups-directory does not exist")
            return []
        records = _directory_messages(client, directory_id)
    except SlackApiError as exc:
        logger.exception("Could not validate group matches against Slack: %s", exc)
        return []

    verified: list[GroupMatch] = []
    for match in matches[:3]:
        channel = match.channel.removeprefix("#").casefold()
        contact = match.contact.removeprefix("@").casefold()
        channel_marker = f"#{channel}"
        contact_marker = f"@{contact}"
        grounded = channel in channels and any(
            channel_marker in record and contact_marker in record for record in records
        )
        if grounded:
            match.channel = channel
            verified.append(match)
        else:
            logger.warning(
                "Rejected ungrounded group match: group=%r contact=%r channel=%r",
                match.group_name,
                match.contact,
                match.channel,
            )
    return verified


async def present_group_matches(
    ctx: RunContext[AgentDeps],
    matches: list[GroupMatch],
    intro_text_localized: str,
    button_label_localized: str,
) -> str:
    """Present matched groups to the user as interactive Block Kit cards.

    Call this AFTER searching #groups-directory via the Slack MCP Server.
    Each card shows the group's details with an accept button; clicking it
    triggers the intro post in the group's channel. Also logs the 'matched'
    impact event automatically — do NOT log it yourself.

    After this call succeeds, reply with only a SHORT closing sentence in the
    user's language (e.g. "Just tap a button and I'll introduce you!") —
    do NOT repeat the group details in text.

    Args:
        ctx: The run context with dependencies.
        matches: The top 2–3 matched groups, best match first.
        intro_text_localized: One friendly lead-in sentence in the user's
            language, e.g. "I found these groups for you:".
        button_label_localized: The accept-button label in the user's language,
            e.g. "Introduce me", "Preséntame", "عرّفني".
    """
    deps = ctx.deps
    if not matches:
        return "No matches to present — tell the user nothing was found and suggest alternatives."

    matches = _verified_matches(deps.client, matches)
    if not matches:
        return (
            "No verified directory matches were found. Tell the user you could not find "
            "an exact current group and suggest trying another interest. Do not invent one."
        )

    blocks: list[dict] = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{intro_text_localized}*"},
        },
        {"type": "divider"},
    ]

    for match in matches[:3]:
        details = [f"*{match.emoji} {match.group_name}*"]
        if match.schedule:
            details.append(
                f"📅 {match.schedule}"
                + (f"  ·  🏠 {match.location}" if match.location else "")
            )
        if match.languages:
            details.append(f"🌍 {match.languages}")
        details.append(f"👤 {match.contact}  ·  📢 #{match.channel}")
        details.append(f"_{match.description_localized}_")

        # Button value must stay small (2000-char limit) — carry only what the
        # accept handler needs to post the intro.
        value = json.dumps(
            {
                "group": match.group_name,
                "contact": match.contact,
                "channel": match.channel,
            }
        )
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(details)},
                "accessory": {
                    "type": "button",
                    "style": "primary",
                    "action_id": "accept_intro",
                    "text": {
                        "type": "plain_text",
                        "text": f"🤝 {button_label_localized}"[:75],
                        "emoji": True,
                    },
                    "value": value,
                },
            }
        )
        blocks.append({"type": "divider"})

    try:
        deps.client.chat_postMessage(
            channel=deps.channel_id,
            thread_ts=deps.thread_ts or None,
            text=intro_text_localized,
            blocks=blocks,
        )
    except SlackApiError as e:
        return f"Could not post the match cards: {e.response['error']}"

    user_store.log_event(
        "matched",
        deps.user_id,
        metadata={"groups": [m.group_name for m in matches[:3]]},
    )
    return (
        f"Posted {len(matches[:3])} match card(s) with intro buttons. "
        "Now reply with one short closing sentence in the user's language."
    )
