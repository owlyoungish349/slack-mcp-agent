import os
from logging import Logger
from urllib.parse import urljoin

from slack_bolt import BoltContext
from slack_sdk import WebClient

from listeners.utils import get_user_token
from listeners.views.app_home_builder import build_app_home_view


def handle_app_home_opened(client: WebClient, context: BoltContext, logger: Logger):
    """Publish the App Home view when a user opens the app's Home tab."""
    try:
        user_id = context.user_id
        # Socket Mode uses the operator's configured user token when a
        # per-user OAuth token is unavailable.  This is the same token path
        # used by the agent's MCP tools, so the Home status must reflect it.
        is_connected = bool(get_user_token(context))
        install_url = None

        if not is_connected and os.environ.get("SLACK_CLIENT_ID"):
            redirect_uri = os.environ.get("SLACK_REDIRECT_URI", "")
            install_url = urljoin(redirect_uri, "/slack/install")

        view = build_app_home_view(install_url=install_url, is_connected=is_connected)
        client.views_publish(user_id=user_id, view=view)
    except Exception as e:
        logger.exception(f"Failed to publish App Home: {e}")
