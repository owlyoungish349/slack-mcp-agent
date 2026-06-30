import os

from slack_bolt import BoltContext


def get_user_token(context: BoltContext) -> str | None:
    """Return the user-scoped OAuth token, falling back to SLACK_USER_TOKEN from env.

    In Socket Mode without OAuth, context.user_token is always None.
    Set SLACK_USER_TOKEN in your .env (the operator's personal user token) so
    the Slack MCP Server and user-scoped API calls work without per-user OAuth.
    """
    return context.user_token or os.environ.get("SLACK_USER_TOKEN")
