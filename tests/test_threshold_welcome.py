from unittest.mock import Mock

from listeners.commands.threshold_welcome import _resolve_target_user_id


def test_resolves_encoded_slack_mention():
    client = Mock()

    user_id = _resolve_target_user_id("<@U012ABC|alex>", {}, client)

    assert user_id == "U012ABC"
    client.users_list.assert_not_called()


def test_resolves_raw_username_from_unescaped_slash_command():
    client = Mock()
    client.users_list.return_value = {
        "members": [
            {
                "id": "U012ABC",
                "name": "alex",
                "profile": {"display_name": "Alex", "real_name": "Alex Smith"},
            }
        ]
    }

    user_id = _resolve_target_user_id("@alex", {}, client)

    assert user_id == "U012ABC"


def test_resolves_display_name_case_insensitively():
    client = Mock()
    client.users_list.return_value = {
        "members": [
            {
                "id": "U012ABC",
                "name": "alex",
                "profile": {"display_name": "Alex S", "real_name": "Alex Smith"},
            }
        ]
    }

    user_id = _resolve_target_user_id("@ALEX S", {}, client)

    assert user_id == "U012ABC"


def test_resolves_me_to_command_invoker():
    client = Mock()

    user_id = _resolve_target_user_id("me", {"user_id": "U999"}, client)

    assert user_id == "U999"
    client.users_list.assert_not_called()


def test_returns_none_for_unknown_user():
    client = Mock()
    client.users_list.return_value = {"members": []}

    assert _resolve_target_user_id("@missing", {}, client) is None
