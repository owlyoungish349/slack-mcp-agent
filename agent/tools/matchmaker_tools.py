"""Flow B — present group matches as interactive Block Kit cards.

The agent finds groups via the Slack MCP Server (search of #groups-directory),
then calls `present_group_matches` to render them as cards with an
"Introduce me" button. The button click is handled by
listeners/actions/accept_intro.py, which asks the agent to post the intro
via MCP in the group's channel.
"""

import json

from pydantic import BaseModel, Field
from pydantic_ai import RunContext
from slack_sdk.errors import SlackApiError

from agent.deps import AgentDeps
from store import user_store


class GroupMatch(BaseModel):
    """One matched group from the #groups-directory search."""

    group_name: str = Field(description="Group name, e.g. 'Café Volunteering'")
    emoji: str = Field(default="🤝", description="One emoji that fits the group, e.g. '☕'")
    schedule: str = Field(description="When it meets, e.g. 'Sundays 9:30–12:00'")
    location: str = Field(default="", description="Where it meets, e.g. 'Church Café'")
    languages: str = Field(default="", description="Languages supported, e.g. 'All languages welcome'")
    contact: str = Field(description="Contact person's name/handle from the directory, e.g. 'james-t'")
    channel: str = Field(description="The group's channel name WITHOUT '#', e.g. 'cafe-volunteers'")
    description_localized: str = Field(
        description="1–2 sentence description of the group, written in the USER'S preferred language"
    )


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
            details.append(f"📅 {match.schedule}" + (f"  ·  🏠 {match.location}" if match.location else ""))
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
