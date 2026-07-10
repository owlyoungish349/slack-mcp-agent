import logging
from unittest.mock import Mock, patch

from slack_bolt import BoltContext
from slack_sdk import WebClient

from listeners.events.app_home_opened import handle_app_home_opened

test_logger = logging.getLogger(__name__)


class TestAppHomeOpened:
    def setup_method(self):
        self.fake_client = Mock(WebClient)
        self.fake_context = Mock(BoltContext)
        self.fake_context.user_id = "U123"

    def test_publishes_home_view(self):
        handle_app_home_opened(
            client=self.fake_client,
            context=self.fake_context,
            logger=test_logger,
        )

        self.fake_client.views_publish.assert_called_once()
        kwargs = self.fake_client.views_publish.call_args.kwargs
        assert kwargs["user_id"] == "U123"
        assert kwargs["view"]["type"] == "home"

    @patch("listeners.events.app_home_opened.get_user_token", return_value="xoxp-test")
    def test_marks_mcp_connected_when_configured_token_is_available(self, _token):
        handle_app_home_opened(
            client=self.fake_client,
            context=self.fake_context,
            logger=test_logger,
        )

        view = self.fake_client.views_publish.call_args.kwargs["view"]
        status_texts = [
            block.get("text", {}).get("text", "") for block in view["blocks"]
        ]
        assert any("Slack MCP Server is connected." in text for text in status_texts)

    def test_views_publish_exception(self, caplog):
        self.fake_client.views_publish.side_effect = Exception("test exception")

        handle_app_home_opened(
            client=self.fake_client,
            context=self.fake_context,
            logger=test_logger,
        )

        self.fake_client.views_publish.assert_called_once()
        assert "test exception" in caplog.text
