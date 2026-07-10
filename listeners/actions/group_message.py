"""Write to a group — compose in any language, Threshold posts it in English.

The App Home button opens a modal with a message input and a channel picker.
On submit, the message is translated into English, posted to the chosen
channel through the Slack MCP Server with clear attribution, and the user
receives a private confirmation in their own language.
"""

import asyncio
from logging import Logger

from pydantic_ai.mcp import MCPServerStreamableHTTP
from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from agent.translation import translate_text
from listeners.utils import get_user_token
from store import user_store

_SLACK_MCP_URL = "https://mcp.slack.com/mcp"

_GROUP_MESSAGE_CALLBACK_ID = "group_message_submit"
_TEXT_BLOCK_ID = "group_message_text"
_TEXT_ACTION_ID = "text"
_CHANNEL_BLOCK_ID = "group_message_channel"
_CHANNEL_ACTION_ID = "channel"

_CONFIRMATIONS = {
    "en": "Done! I posted your message in <#{channel_id}> in English.",
    "es": "¡Listo! Publiqué tu mensaje en <#{channel_id}> en inglés.",
    "ar": "تم! نشرت رسالتك في <#{channel_id}> بالإنجليزية.",
    "pl": "Gotowe! Opublikowałem Twoją wiadomość na <#{channel_id}> po angielsku.",
    "pt": "Pronto! Publiquei sua mensagem em <#{channel_id}> em inglês.",
    "ro": "Gata! Am publicat mesajul tău în <#{channel_id}> în engleză.",
    "fa": "انجام شد! پیام شما را به انگلیسی در <#{channel_id}> ارسال کردم.",
}


def build_group_message_modal() -> dict:
    """Build a modal with a message input and a destination channel picker."""
    return {
        "type": "modal",
        "callback_id": _GROUP_MESSAGE_CALLBACK_ID,
        "title": {"type": "plain_text", "text": "Write to a group", "emoji": True},
        "submit": {"type": "plain_text", "text": "Send", "emoji": True},
        "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
        "blocks": [
            {
                "type": "input",
                "block_id": _TEXT_BLOCK_ID,
                "label": {
                    "type": "plain_text",
                    "text": "Your message — any language",
                    "emoji": True,
                },
                "hint": {
                    "type": "plain_text",
                    "text": "I'll translate it into English and post it for you.",
                    "emoji": True,
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": _TEXT_ACTION_ID,
                    "multiline": True,
                    "max_length": 3000,
                },
            },
            {
                "type": "input",
                "block_id": _CHANNEL_BLOCK_ID,
                "label": {"type": "plain_text", "text": "Post to", "emoji": True},
                "element": {
                    "type": "channels_select",
                    "action_id": _CHANNEL_ACTION_ID,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Choose a channel…",
                        "emoji": True,
                    },
                },
            },
        ],
    }


def handle_open_group_message(
    ack: Ack, body: dict, client: WebClient, logger: Logger
) -> None:
    """Open the group-message composer from the App Home button."""
    ack()
    try:
        client.views_open(
            trigger_id=body["trigger_id"], view=build_group_message_modal()
        )
    except SlackApiError as exc:
        logger.exception(
            "Could not open group message modal for %s: %s", body["user"]["id"], exc
        )


async def _post_message_via_mcp(user_token: str, channel_id: str, message: str) -> None:
    server = MCPServerStreamableHTTP(
        _SLACK_MCP_URL,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    await server.direct_call_tool(
        "slack_send_message",
        {"channel_id": channel_id, "message": message},
    )


def _build_channel_message(user_id: str, translated: str) -> str:
    return f"🌐 <@{user_id}> says (translated by Threshold): {translated}"


def _confirmation(language_code: str, channel_id: str) -> str:
    template = _CONFIRMATIONS.get(language_code, _CONFIRMATIONS["en"])
    return template.format(channel_id=channel_id)


def handle_group_message_submission(
    ack: Ack,
    body: dict,
    client: WebClient,
    context: BoltContext,
    logger: Logger,
) -> None:
    """Translate the submitted message to English and post it to the channel."""
    values = body["view"]["state"]["values"]
    source_text = values[_TEXT_BLOCK_ID][_TEXT_ACTION_ID]["value"].strip()
    if not source_text:
        ack(
            response_action="errors",
            errors={_TEXT_BLOCK_ID: "Enter a message to send."},
        )
        return

    channel_id = values[_CHANNEL_BLOCK_ID][_CHANNEL_ACTION_ID]["selected_channel"]
    user_id = body["user"]["id"]
    ack()

    lang_code, _lang_name = user_store.get_language(user_id)
    try:
        user_token = get_user_token(context)
        if not user_token:
            raise RuntimeError("No Slack user token available for MCP")

        translated = translate_text(source_text, "English")
        asyncio.run(
            _post_message_via_mcp(
                user_token, channel_id, _build_channel_message(user_id, translated)
            )
        )

        user_store.log_event(
            "message_posted",
            user_id,
            lang_code,
            metadata={"detail": channel_id},
        )
        dm_channel = client.conversations_open(users=user_id)["channel"]["id"]
        confirmation = _confirmation(lang_code, channel_id)
        client.chat_postMessage(
            channel=dm_channel,
            text=confirmation,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"✅ {confirmation}"},
                }
            ],
        )
        logger.info("Group message posted for %s -> %s", user_id, channel_id)
    except Exception as exc:
        logger.exception("Group message failed for %s: %s", user_id, exc)
        try:
            dm_channel = client.conversations_open(users=user_id)["channel"]["id"]
            client.chat_postMessage(
                channel=dm_channel,
                text="⚠️ I couldn't send your message just now. Please try again in a moment.",
            )
        except SlackApiError:
            logger.exception(
                "Could not notify %s about a failed group message", user_id
            )
