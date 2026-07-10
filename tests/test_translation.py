from unittest.mock import Mock, patch

from listeners.actions.translation import (
    build_translation_modal,
    handle_translation_submission,
)


def _submission_body(text: str = "Welcome") -> dict:
    return {
        "user": {"id": "U123"},
        "view": {
            "state": {
                "values": {
                    "translation_text": {"text": {"value": text}},
                    "translation_language": {
                        "language": {"selected_option": {"value": "fa|فارسی"}}
                    },
                }
            }
        },
    }


def test_translation_modal_defaults_to_saved_language_and_supports_persian():
    modal = build_translation_modal("Hello", "fa")

    language_element = modal["blocks"][1]["element"]
    assert language_element["initial_option"]["value"] == "fa|فارسی"
    assert any(option["value"] == "fa|فارسی" for option in language_element["options"])


@patch("listeners.actions.translation.translate_text", return_value="خوش آمدید")
def test_translation_submission_sends_private_result(translate):
    client = Mock()
    client.conversations_open.return_value = {"channel": {"id": "D123"}}
    ack = Mock()

    handle_translation_submission(ack, _submission_body(), client, Mock())

    ack.assert_called_once_with()
    translate.assert_called_once_with("Welcome", "فارسی")
    client.chat_postMessage.assert_called_once()
    assert "خوش آمدید" in client.chat_postMessage.call_args.kwargs["text"]


def test_translation_submission_rejects_empty_text():
    ack = Mock()

    handle_translation_submission(ack, _submission_body("   "), Mock(), Mock())

    ack.assert_called_once_with(
        response_action="errors",
        errors={"translation_text": "Enter text to translate."},
    )
