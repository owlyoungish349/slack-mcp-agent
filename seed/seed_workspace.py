#!/usr/bin/env python3
"""Threshold seed script — populates the Slack workspace with demo channels and content.

Usage:
    python -m seed.seed_workspace

Requires SLACK_BOT_TOKEN in your environment (or .env file).
The bot must have been added to the workspace and have the following scopes:
  channels:manage, channels:read, chat:write, groups:write (for private channels)

What this creates:
  Channels: #welcome, #announcements, #groups-directory,
            #english-circle, #cafe-volunteers, #prayer-group,
            #family-group, #arabic-community
  Content:  6 group directory entries in #groups-directory
            4 sample announcements in #announcements
"""

import os
import sys
import time

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv(dotenv_path=".env", override=False)

CHANNELS = [
    ("welcome", "Welcome new members here"),
    ("announcements", "Church-wide announcements"),
    ("groups-directory", "Directory of life groups, classes, and volunteering"),
    ("english-circle", "English Conversation Circle — weekly practice group"),
    ("cafe-volunteers", "Sunday café volunteering team"),
    ("prayer-group", "Weekly prayer and reflection group"),
    ("family-group", "Families and children's group"),
    ("arabic-community", "Arabic-speaking community group"),
]

GROUP_DIRECTORY_ENTRIES = [
    """\
*English Conversation Circle* 🗣️
📅 Wednesdays 7:00–8:30pm | 🏠 Church Hall Room 2
🌍 All levels welcome — absolute beginners especially!
👤 Contact: @maria-g | 📢 #english-circle
A warm, relaxed weekly group for practising conversational English over tea and biscuits. No experience needed — just bring yourself.
`Tags: english, language, learning, weekly`""",
    """\
*Café Volunteering* ☕
📅 Sundays 9:30–12:00 | 🏠 Church Café
🌍 All languages welcome
👤 Contact: @james-t | 📢 #cafe-volunteers
Help serve coffee and welcome people on Sunday mornings. A wonderful way to meet the community while making a difference. Training provided.
`Tags: volunteering, café, sunday, serving`""",
    """\
*Families & Children's Group* 👨‍👩‍👧
📅 Thursdays 4:00–5:30pm | 🏠 Church Garden (weather permitting)
🌍 English + Español | Niños bienvenidos
👤 Contact: @elena-r | 📢 #family-group
A relaxed afternoon for parents and young children to meet, play, and connect. Bilingual (EN/ES) sessions. Snacks provided.
`Tags: family, children, parents, spanish, bilingual`""",
    """\
*Prayer Group* 🙏
📅 Tuesdays 7:00–8:00pm | 🏠 Chapel
🌍 All welcome
👤 Contact: @pastor-john | 📢 #prayer-group
A quiet, open space for communal prayer and reflection. All traditions and backgrounds welcome.
`Tags: prayer, quiet, weekly, spiritual`""",
    """\
*New Members Fellowship* 🤝
📅 Last Sunday of the month, 12:30–2:00pm | 🏠 Church Lounge
🌍 English (translation support available on request)
👤 Contact: @sarah-c | 📢 #welcome
A relaxed lunch gathering specifically for people who have recently joined. A perfect first step into the community.
`Tags: new members, lunch, monthly, welcome, social`""",
    """\
*Arabic Community Group* 🌙
📅 Saturdays 3:00–5:00pm | 🏠 Room 5
🌍 Arabic + English
👤 Contact: @amir-k | 📢 #arabic-community
A welcoming space for Arabic-speaking members to connect, share culture, and support each other. Refreshments served.
`Tags: arabic, community, cultural, weekly`""",
]

ANNOUNCEMENTS = [
    "📣 *Summer Fete — Saturday 5th July, 11am–3pm* on the church grounds. Games, food stalls, and live music. Helpers needed from 10am — message @james-t if you can assist!",
    "📖 *New Bible Study Series starting Wednesday 9th July* — 'Finding Your Footing: Faith in Uncertain Times'. All welcome, no prior knowledge needed. Copies available from the foyer.",
    "🥫 *Food Bank Collection this Sunday* — Please bring tinned goods, pasta, or long-life milk to the service. Items go directly to local families in need.",
    "🏢 *Church Office Closed Monday 30th June* for a staff training day. For urgent matters please email admin@cornerstonechurch.example.",
]


def find_or_create_channel(client: WebClient, name: str, purpose: str) -> str | None:
    """Return the channel ID, creating it if it doesn't exist."""
    # Try to find existing channel
    try:
        cursor = None
        while True:
            resp = client.conversations_list(
                limit=200,
                exclude_archived=True,
                types="public_channel",
                cursor=cursor,
            )
            for ch in resp["channels"]:
                if ch["name"] == name:
                    print(f"  ✓ #{name} already exists ({ch['id']})")
                    return ch["id"]
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except SlackApiError as e:
        print(f"  ⚠ Could not list channels: {e.response['error']}")

    # Create it
    try:
        resp = client.conversations_create(name=name, is_private=False)
        ch_id = resp["channel"]["id"]
        if purpose:
            client.conversations_setPurpose(channel=ch_id, purpose=purpose)
        print(f"  ✓ Created #{name} ({ch_id})")
        return ch_id
    except SlackApiError as e:
        print(f"  ✗ Could not create #{name}: {e.response['error']}")
        return None


def invite_bot_to_channel(client: WebClient, channel_id: str, bot_user_id: str) -> None:
    try:
        client.conversations_invite(channel=channel_id, users=bot_user_id)
    except SlackApiError as e:
        err = e.response["error"]
        if err not in ("already_in_channel", "cant_invite_self"):
            print(f"    ⚠ Could not invite bot: {err}")


def post_missing_messages(
    client: WebClient, channel_id: str, messages: list[str]
) -> int:
    """Post only canonical messages that are not already in the channel."""
    existing_texts: set[str] = set()
    try:
        resp = client.conversations_history(channel=channel_id, limit=100)
        existing_texts = {
            message.get("text", "") for message in resp.get("messages", [])
        }
    except SlackApiError:
        pass

    posted = 0
    for msg in messages:
        if msg in existing_texts:
            continue
        try:
            client.chat_postMessage(channel=channel_id, text=msg, mrkdwn=True)
            posted += 1
            time.sleep(0.5)  # stay well inside rate limits
        except SlackApiError as e:
            print(f"    ⚠ Post failed: {e.response['error']}")

    if posted == 0:
        print("    ℹ Canonical content already present — nothing to post")
    return posted


def main() -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("ERROR: SLACK_BOT_TOKEN not set.")
        sys.exit(1)

    client = WebClient(token=token)

    # Resolve bot user ID
    try:
        bot_user_id = client.auth_test()["user_id"]
        print(f"Bot user ID: {bot_user_id}\n")
    except SlackApiError as e:
        print(f"Auth failed: {e.response['error']}")
        sys.exit(1)

    channel_ids: dict[str, str] = {}

    print("── Creating channels ──────────────────────────────────")
    for name, purpose in CHANNELS:
        ch_id = find_or_create_channel(client, name, purpose)
        if ch_id:
            channel_ids[name] = ch_id
            invite_bot_to_channel(client, ch_id, bot_user_id)

    print("\n── Seeding #groups-directory ───────────────────────────")
    if "groups-directory" in channel_ids:
        posted = post_missing_messages(
            client, channel_ids["groups-directory"], GROUP_DIRECTORY_ENTRIES
        )
        print(f"  Posted {posted} group entries")
    else:
        print("  ✗ #groups-directory not found — skipping")

    print("\n── Seeding #announcements ──────────────────────────────")
    if "announcements" in channel_ids:
        posted = post_missing_messages(
            client, channel_ids["announcements"], ANNOUNCEMENTS
        )
        print(f"  Posted {posted} announcements")
    else:
        print("  ✗ #announcements not found — skipping")

    print("\n── Done ─────────────────────────────────────────────────")
    print("Next steps (manual):")
    print("  1. Invite ~6 demo personas to the sandbox as Members.")
    print("  2. Add the bot to #welcome and #announcements if not already there.")
    print("  3. Run 'python -m seed.reset_workspace' to restore clean demo state.")
    print(
        "  4. Reserve 2 seats for judges: slackhack@salesforce.com and testing@devpost.com"
    )


if __name__ == "__main__":
    main()
