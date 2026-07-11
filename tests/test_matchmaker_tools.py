import asyncio
from unittest.mock import Mock, patch

from agent.tools.matchmaker_tools import GroupMatch, present_group_matches


def _match(group: str, contact: str, channel: str) -> GroupMatch:
    return GroupMatch(
        group_name=group,
        emoji="☕",
        schedule="Sundays",
        location="Church",
        languages="All languages",
        contact=contact,
        channel=channel,
        description_localized="توضیحات گروه",
    )


def _context() -> tuple[Mock, Mock]:
    client = Mock()
    client.conversations_list.return_value = {
        "channels": [
            {"id": "C-DIRECTORY", "name": "groups-directory"},
            {"id": "C-CAFE", "name": "cafe-volunteers"},
        ],
        "response_metadata": {"next_cursor": ""},
    }
    client.conversations_history.return_value = {
        "messages": [
            {
                "text": (
                    "*Café Volunteering* Contact: @james-t | Channel: #cafe-volunteers"
                )
            }
        ],
        "response_metadata": {"next_cursor": ""},
    }
    deps = Mock(
        client=client,
        channel_id="D123",
        thread_ts="1.0",
        user_id="U123",
    )
    return Mock(deps=deps), client


@patch("agent.tools.matchmaker_tools.user_store")
def test_presents_only_channel_and_contact_pairs_grounded_in_directory(store):
    context, client = _context()
    matches = [
        _match("Café Volunteering", "james-t", "cafe-volunteers"),
        _match("Invented Sunday Team", "john-doe", "sunday-service-setup"),
    ]

    result = asyncio.run(
        present_group_matches(context, matches, "گروه‌های پیدا شده", "معرفی کن")
    )

    assert "Posted 1 match card" in result
    posted = client.chat_postMessage.call_args.kwargs
    rendered = str(posted["blocks"])
    assert "cafe-volunteers" in rendered
    assert "sunday-service-setup" not in rendered
    store.log_event.assert_called_once()
    assert store.log_event.call_args.kwargs["metadata"] == {
        "groups": ["Café Volunteering"]
    }


@patch("agent.tools.matchmaker_tools.user_store")
def test_rejects_all_ungrounded_matches_without_posting_or_logging(store):
    context, client = _context()

    result = asyncio.run(
        present_group_matches(
            context,
            [_match("Invented Sunday Team", "john-doe", "sunday-service-setup")],
            "گروه‌های پیدا شده",
            "معرفی کن",
        )
    )

    assert "No verified directory matches" in result
    client.chat_postMessage.assert_not_called()
    store.log_event.assert_not_called()
