import json
from unittest.mock import AsyncMock, Mock, patch

from listeners.actions.accept_intro import (
    _FAILURES,
    _INTRODUCING,
    _build_intro_message,
    _confirmation,
    _localized,
    handle_accept_intro,
)


def _body() -> dict:
    return {
        "actions": [
            {
                "value": json.dumps(
                    {
                        "group": "Café Volunteering",
                        "contact": "james-t",
                        "channel": "cafe-volunteers",
                    }
                )
            }
        ],
        "user": {"id": "U123"},
        "container": {"channel_id": "D123", "message_ts": "1.2"},
        "message": {"thread_ts": "1.0"},
    }


def test_build_intro_message_mentions_newcomer_and_names_contact():
    message = _build_intro_message("U123", "Café Volunteering", "james-t")

    assert "<@U123>" in message
    assert "@james-t" in message
    assert "Café Volunteering" in message


def test_confirmation_uses_saved_language():
    assert "¡Listo!" in _confirmation("es", "cafe-volunteers")
    assert "#cafe-volunteers" in _confirmation("es", "cafe-volunteers")


def test_persian_progress_and_failure_feedback_are_localized():
    assert "در حال معرفی" in _localized(_INTRODUCING, "fa", group="گروه")
    assert "نتوانستم" in _localized(_FAILURES, "fa")


@patch(
    "listeners.actions.accept_intro._post_intro_via_mcp",
    new_callable=AsyncMock,
)
@patch("listeners.actions.accept_intro._find_channel_id", return_value="C456")
@patch("listeners.actions.accept_intro.get_user_token", return_value="xoxp-test")
@patch("listeners.actions.accept_intro.user_store")
def test_logs_impact_only_after_mcp_success(
    user_store, _get_token, _find_channel, post_intro
):
    user_store.get_language.return_value = ("es", "Español")
    client = Mock()

    handle_accept_intro(
        ack=Mock(),
        body=_body(),
        client=client,
        context=Mock(),
        logger=Mock(),
    )

    post_intro.assert_awaited_once()
    user_store.log_event.assert_called_once()
    client.chat_postMessage.assert_called_once()


@patch(
    "listeners.actions.accept_intro._post_intro_via_mcp",
    new_callable=AsyncMock,
    side_effect=RuntimeError("not_in_channel"),
)
@patch("listeners.actions.accept_intro._find_channel_id", return_value="C456")
@patch("listeners.actions.accept_intro.get_user_token", return_value="xoxp-test")
@patch("listeners.actions.accept_intro.user_store")
def test_does_not_log_impact_when_mcp_post_fails(
    user_store, _get_token, _find_channel, post_intro
):
    user_store.get_language.return_value = ("es", "Español")
    client = Mock()

    handle_accept_intro(
        ack=Mock(),
        body=_body(),
        client=client,
        context=Mock(),
        logger=Mock(),
    )

    post_intro.assert_awaited_once()
    user_store.log_event.assert_not_called()
    client.chat_postMessage.assert_not_called()
