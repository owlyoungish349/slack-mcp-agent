#!/usr/bin/env python3
"""Threshold reset script — restores the workspace to a clean demo state.

What it does:
  1. Wipes the local SQLite impact store (user prefs + events).
  2. Deletes all bot-posted messages from #groups-directory and #announcements,
     then re-seeds them with the canonical demo content.
  3. Prints a checklist for manual steps (remove extra members, etc.).

Usage:
    python -m seed.reset_workspace

Requires SLACK_BOT_TOKEN in your .env.
"""

import os
import sys
import time

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv(dotenv_path=".env", override=False)

# Import store so we can wipe it
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from store import user_store  # noqa: E402
from seed.seed_workspace import (  # noqa: E402
    ANNOUNCEMENTS,
    GROUP_DIRECTORY_ENTRIES,
    find_or_create_channel,
    invite_bot_to_channel,
)


def delete_bot_messages(client: WebClient, channel_id: str, bot_user_id: str) -> int:
    """Delete all messages posted by the bot in this channel. Returns count deleted."""
    deleted = 0
    cursor = None
    while True:
        try:
            resp = client.conversations_history(
                channel=channel_id, limit=200, cursor=cursor
            )
        except SlackApiError as e:
            print(f"  ⚠ Could not read history: {e.response['error']}")
            break

        for msg in resp.get("messages", []):
            if msg.get("bot_id") or msg.get("user") == bot_user_id:
                try:
                    client.chat_delete(channel=channel_id, ts=msg["ts"])
                    deleted += 1
                    time.sleep(0.3)
                except SlackApiError as e:
                    err = e.response["error"]
                    if err not in ("message_not_found", "cant_delete_message"):
                        print(f"  ⚠ Delete failed: {err}")

        cursor = resp.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    return deleted


def post_messages(client: WebClient, channel_id: str, messages: list[str]) -> None:
    for msg in messages:
        try:
            client.chat_postMessage(channel=channel_id, text=msg, mrkdwn=True)
            time.sleep(0.5)
        except SlackApiError as e:
            print(f"  ⚠ Post failed: {e.response['error']}")


def wipe_store() -> None:
    """Delete and reinitialise the SQLite impact store."""
    from pathlib import Path

    db = Path(os.environ.get("THRESHOLD_DATA_DIR", "./data")) / "threshold.db"
    if db.exists():
        db.unlink()
        print("  ✓ Wiped threshold.db")
    else:
        print("  ℹ No threshold.db found — nothing to wipe")
    user_store.init_db()
    print("  ✓ Re-initialised empty database")


def main() -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("ERROR: SLACK_BOT_TOKEN not set.")
        sys.exit(1)

    client = WebClient(token=token)

    try:
        auth = client.auth_test()
        bot_user_id = auth["user_id"]
        print(f"Bot user ID: {bot_user_id}\n")
    except SlackApiError as e:
        print(f"Auth failed: {e.response['error']}")
        sys.exit(1)

    print("── Wiping impact store ─────────────────────────────────")
    wipe_store()

    RESEED_CHANNELS = [
        ("groups-directory", GROUP_DIRECTORY_ENTRIES, "group entries"),
        ("announcements", ANNOUNCEMENTS, "announcements"),
    ]

    for ch_name, entries, label in RESEED_CHANNELS:
        print(f"\n── Resetting #{ch_name} ({'─' * (40 - len(ch_name))})")
        ch_id = find_or_create_channel(client, ch_name, "")
        if not ch_id:
            print(f"  ✗ Could not find/create #{ch_name}")
            continue
        invite_bot_to_channel(client, ch_id, bot_user_id)
        n = delete_bot_messages(client, ch_id, bot_user_id)
        print(f"  ✓ Deleted {n} bot message(s)")
        post_messages(client, ch_id, entries)
        print(f"  ✓ Re-posted {len(entries)} {label}")

    print("\n── Done ─────────────────────────────────────────────────")
    print("Manual steps before the next demo:")
    print("  1. Ensure demo personas are still members of the workspace.")
    print("  2. Clear any DM history with the bot for each persona (Slack UI).")
    print("  3. The impact dashboard (/threshold-impact) now shows zeroes — ready.")
