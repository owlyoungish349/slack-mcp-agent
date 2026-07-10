from unittest.mock import Mock

from listeners.actions.start_conversation import handle_start_conversation


def test_start_conversation_sends_language_picker_to_the_user_dm():
    client = Mock()
    client.users_info.return_value = {
        "user": {"profile": {"display_name": "Sam"}, "real_name": "Sam"}
    }
    client.conversations_open.return_value = {"channel": {"id": "D123"}}
    ack = Mock()

    handle_start_conversation(
        ack,
        {"user": {"id": "U123"}},
        client,
        Mock(),
    )

    ack.assert_called_once_with()
    client.conversations_open.assert_called_once_with(users="U123")
    posted = client.chat_postMessage.call_args.kwargs
    assert posted["channel"] == "D123"
    assert posted["blocks"][1]["elements"][0]["action_id"] == "language_select"
