from unittest.mock import Mock, patch

from listeners.commands.threshold_impact import handle_threshold_impact


@patch("listeners.commands.threshold_impact.user_store.get_impact_summary")
def test_responds_via_slash_command_response_url(get_summary):
    get_summary.return_value = {
        "welcomed": 1,
        "matched": 1,
        "intro_made": 1,
        "digest_sent": 0,
        "languages_served": ["es"],
        "referrals_needed": 0,
        "avg_connection_seconds": 30,
    }
    ack = Mock()
    respond = Mock()

    handle_threshold_impact(ack=ack, respond=respond, logger=Mock())

    ack.assert_called_once_with()
    respond.assert_called_once()
    assert respond.call_args.kwargs["response_type"] == "ephemeral"
    assert respond.call_args.kwargs["blocks"]


@patch(
    "listeners.commands.threshold_impact.user_store.get_impact_summary",
    side_effect=RuntimeError("database unavailable"),
)
def test_returns_ephemeral_error_when_dashboard_fails(_get_summary):
    respond = Mock()

    handle_threshold_impact(ack=Mock(), respond=respond, logger=Mock())

    respond.assert_called_once_with(
        text="⚠️ I couldn't load the impact dashboard just now.",
        response_type="ephemeral",
    )
