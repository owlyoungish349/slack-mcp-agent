"""On-demand translation from the App Home and Slack message shortcuts."""

from logging import Logger

from slack_bolt import Ack
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from agent.translation import translate_text
from listeners.views.threshold_blocks import LANGUAGE_OPTIONS
from store import user_store

_TRANSLATION_CALLBACK_ID = "translate_text_submit"
_TEXT_BLOCK_ID = "translation_text"
_TEXT_ACTION_ID = "text"
_LANGUAGE_BLOCK_ID = "translation_language"
_LANGUAGE_ACTION_ID = "language"


def _language_option(code: str, name: str, flag: str) -> dict:
    return {
        "text": {"type": "plain_text", "text": f"{flag} {name}", "emoji": True},
        "value": f"{code}|{name}",
    }


def build_translation_modal(source_text: str, language_code: str) -> dict:
    """Build a modal with pre-filled source text and the saved target language."""
    options = [_language_option(*option) for option in LANGUAGE_OPTIONS]
    initial_option = next(
        (
            option
            for option in options
            if option["value"].startswith(f"{language_code}|")
        ),
        options[0],
    )
    return {
        "type": "modal",
        "callback_id": _TRANSLATION_CALLBACK_ID,
        "title": {"type": "plain_text", "text": "Translate", "emoji": True},
        "submit": {"type": "plain_text", "text": "Translate", "emoji": True},
        "close": {"type": "plain_text", "text": "Cancel", "emoji": True},
        "blocks": [
            {
                "type": "input",
                "block_id": _TEXT_BLOCK_ID,
                "label": {
                    "type": "plain_text",
                    "text": "Text to translate",
                    "emoji": True,
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": _TEXT_ACTION_ID,
                    "multiline": True,
                    "initial_value": source_text[:3000],
                    "max_length": 3000,
                },
            },
            {
                "type": "input",
                "block_id": _LANGUAGE_BLOCK_ID,
                "label": {
                    "type": "plain_text",
                    "text": "Translate into",
                    "emoji": True,
                },
                "element": {
                    "type": "static_select",
                    "action_id": _LANGUAGE_ACTION_ID,
                    "options": options,
                    "initial_option": initial_option,
                },
            },
        ],
    }


def _open_translation_modal(
    body: dict, client: WebClient, source_text: str, logger: Logger
) -> None:
    user_id = body["user"]["id"]
    language_code, _language_name = user_store.get_language(user_id)
    try:
        client.views_open(
            trigger_id=body["trigger_id"],
            view=build_translation_modal(source_text, language_code),
        )
    except SlackApiError as exc:
        logger.exception("Could not open translation modal for %s: %s", user_id, exc)


def handle_open_translation(
    ack: Ack, body: dict, client: WebClient, logger: Logger
) -> None:
    """Open the translator from the App Home button."""
    ack()
    _open_translation_modal(body, client, "", logger)


def handle_translate_shortcut(
    ack: Ack, body: dict, client: WebClient, logger: Logger
) -> None:
    """Open the translator with text from a selected Slack message."""
    ack()
    _open_translation_modal(
        body, client, body.get("message", {}).get("text", ""), logger
    )


def handle_translation_submission(
    ack: Ack, body: dict, client: WebClient, logger: Logger
) -> None:
    """Translate submitted text and deliver the private result in a Threshold DM."""
    values = body["view"]["state"]["values"]
    source_text = values[_TEXT_BLOCK_ID][_TEXT_ACTION_ID]["value"].strip()
    if not source_text:
        ack(
            response_action="errors",
            errors={_TEXT_BLOCK_ID: "Enter text to translate."},
        )
        return

    selected = values[_LANGUAGE_BLOCK_ID][_LANGUAGE_ACTION_ID]["selected_option"]
    _language_code, language_name = selected["value"].split("|", 1)
    user_id = body["user"]["id"]
    ack()

    try:
        translated = translate_text(source_text, language_name)
        dm_channel = client.conversations_open(users=user_id)["channel"]["id"]
        client.chat_postMessage(
            channel=dm_channel,
            text=f"Translation ({language_name}): {translated}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Translation — {language_name}*\n{translated}",
                    },
                }
            ],
        )
    except Exception as exc:
        logger.exception("Translation failed for %s: %s", user_id, exc)
        try:
            dm_channel = client.conversations_open(users=user_id)["channel"]["id"]
            client.chat_postMessage(
                channel=dm_channel,
                text="⚠️ I couldn't translate that just now. Please try again in a moment.",
            )
        except SlackApiError:
            logger.exception("Could not notify %s about a failed translation", user_id)
