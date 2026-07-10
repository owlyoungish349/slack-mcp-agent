from unittest.mock import Mock, patch

from seed.seed_workspace import post_missing_messages


@patch("seed.seed_workspace.time.sleep")
def test_posts_seed_content_when_channel_only_has_system_history(_sleep):
    client = Mock()
    client.conversations_history.return_value = {
        "messages": [{"subtype": "channel_join", "text": "A member joined"}]
    }

    posted = post_missing_messages(client, "C123", ["first", "second"])

    assert posted == 2
    assert client.chat_postMessage.call_count == 2


@patch("seed.seed_workspace.time.sleep")
def test_posts_only_missing_seed_content(_sleep):
    client = Mock()
    client.conversations_history.return_value = {"messages": [{"text": "first"}]}

    posted = post_missing_messages(client, "C123", ["first", "second"])

    assert posted == 1
    client.chat_postMessage.assert_called_once_with(
        channel="C123", text="second", mrkdwn=True
    )


def test_skips_seed_content_already_present():
    client = Mock()
    client.conversations_history.return_value = {
        "messages": [{"text": "first"}, {"text": "second"}]
    }

    posted = post_missing_messages(client, "C123", ["first", "second"])

    assert posted == 0
    client.chat_postMessage.assert_not_called()
