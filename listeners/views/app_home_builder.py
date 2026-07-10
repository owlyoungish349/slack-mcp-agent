def build_app_home_view(
    install_url: str | None = None, is_connected: bool = False
) -> dict:
    """Build the App Home Block Kit view.

    Args:
        install_url: OAuth install URL. When provided, the user has not
            connected and will see a link to install.
        is_connected: When ``True``, the user is connected and the MCP
            status section shows as connected.
    """
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "Threshold 🙏 — your guide to belonging",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Welcome to Cornerstone Community Church!* I help newcomers find "
                    "their place — life groups, English classes, volunteering, and "
                    "community — *in your own language*, no referral needed.\n\n"
                    "🇬🇧 English · 🇪🇸 Español · 🇸🇦 العربية · 🇵🇱 Polski · 🇧🇷 Português · 🇷🇴 Română · 🇮🇷 فارسی"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Start chatting",
                        "emoji": True,
                    },
                    "action_id": "start_conversation",
                    "style": "primary",
                    "value": "start_conversation",
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Translate text",
                        "emoji": True,
                    },
                    "action_id": "open_translation",
                    "value": "open_translation",
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Write to a group",
                        "emoji": True,
                    },
                    "action_id": "open_group_message",
                    "value": "open_group_message",
                },
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": "*💬 Message me*\nTell me what you're looking for — in any language — and I'll find matching groups.",
                },
                {
                    "type": "mrkdwn",
                    "text": "*🤝 Get introduced*\nTap *Introduce me* on a group card and I'll connect you with a real person.",
                },
                {
                    "type": "mrkdwn",
                    "text": "*📢 `/threshold-digest`*\nThis week's announcements, translated into your language.",
                },
                {
                    "type": "mrkdwn",
                    "text": "*📊 `/threshold-impact`*\nSee how many people Threshold has helped get connected.",
                },
            ],
        },
        {"type": "divider"},
    ]

    if is_connected:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\U0001f7e2 *Slack MCP Server is connected.*",
                },
            }
        )
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "The agent can search messages, read channels, and more.",
                    }
                ],
            }
        )
    elif install_url:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"\U0001f534 *Slack MCP Server is disconnected.* <{install_url}|Connect the Slack MCP Server.>",
                },
            }
        )
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "The Slack MCP Server enables the agent to search messages, read channels, and more.",
                    }
                ],
            }
        )
    else:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\U0001f534 *Slack MCP Server is disconnected.* <https://github.com/slack-samples/bolt-python-starter-agent/blob/main/pydantic-ai/README.md#slack-mcp-server|Learn how to enable the Slack MCP Server.>",
                },
            }
        )
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "The Slack MCP Server enables the agent to search messages, read channels, and more.",
                    }
                ],
            }
        )

    return {
        "type": "home",
        "blocks": blocks,
    }
