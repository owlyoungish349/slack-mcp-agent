from unittest.mock import Mock, patch

from listeners.actions.group_message import (
    build_group_message_modal,
    handle_group_message_submission,
)


def _submission_body(text: str = "می‌خواهم روزهای یکشنبه داوطلب شوم.") -> dict:
    return {
        "user": {"id": "U123"},
        "view": {
            "state": {
                "values": {
                    "group_message_text": {"text": {"value": text}},
                    "group_message_channel": {
                        "channel": {"selected_channel": "C456"}
                    },
                }
            }
        },
    }


def _context() -> Mock:
    context = Mock()
    context.user_token = "xoxp-test"
    return context


def test_group_message_modal_has_text_input_and_channel_picker():
    modal = build_group_message_modal()

    assert modal["callback_id"] == "group_message_submit"
    assert modal["blocks"][0]["element"]["type"] == "plain_text_input"
    assert modal["blocks"][1]["element"]["type"] == "channels_select"


@patch("listeners.actions.group_message.user_store")
@patch("listeners.actions.group_message.asyncio.run")
@patch("listeners.actions.group_message._post_message_via_mcp", new_callable=Mock)
@patch(
    "listeners.actions.group_message.translate_text",
    return_value="I would like to volunteer on Sundays.",
)
def test_group_message_translates_posts_and_confirms_in_user_language(
    translate, post_mcp, asyncio_run, store
):
    store.get_language.return_value = ("fa", "فارسی")
    client = Mock()
    client.conversations_open.return_value = {"channel": {"id": "D123"}}
    ack = Mock()

    handle_group_message_submission(
        ack, _submission_body(), client, _context(), Mock()
    )

    ack.assert_called_once_with()
    translate.assert_called_once_with(
        "می‌خواهم روزهای یکشنبه داوطلب شوم.", "English"
    )

    token, channel_id, message = post_mcp.call_args.args
    assert token == "xoxp-test"
    assert channel_id == "C456"
    assert "<@U123>" in message
    assert "I would like to volunteer on Sundays." in message

    store.log_event.assert_called_once()
    confirmation = client.chat_postMessage.call_args.kwargs["text"]
    assert "<#C456>" in confirmation
    assert "انجام شد" in confirmation


def test_group_message_rejects_empty_text():
    ack = Mock()

    handle_group_message_submission(
        ack, _submission_body("   "), Mock(), _context(), Mock()
    )

    ack.assert_called_once_with(
        response_action="errors",
        errors={"group_message_text": "Enter a message to send."},
    )


@patch("listeners.actions.group_message.user_store")
@patch(
    "listeners.actions.group_message.asyncio.run",
    side_effect=RuntimeError("mcp down"),
)
@patch("listeners.actions.group_message._post_message_via_mcp", new_callable=Mock)
@patch(
    "listeners.actions.group_message.translate_text",
    return_value="I would like to volunteer on Sundays.",
)
def test_group_message_failure_notifies_user_and_logs_nothing(
    translate, post_mcp, asyncio_run, store
):
    store.get_language.return_value = ("fa", "فارسی")
    client = Mock()
    client.conversations_open.return_value = {"channel": {"id": "D123"}}
    ack = Mock()

    handle_group_message_submission(
        ack, _submission_body(), client, _context(), Mock()
    )

    store.log_event.assert_not_called()
    failure_text = client.chat_postMessage.call_args.kwargs["text"]
    assert "couldn't send" in failure_text
