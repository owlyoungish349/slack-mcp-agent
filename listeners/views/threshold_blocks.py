"""Block Kit builders for Threshold — welcome picker, impact dashboard, group cards."""


# ── Language picker (Flow A) ─────────────────────────────────────────────────

LANGUAGE_OPTIONS = [
    ("en", "English", "🇬🇧"),
    ("es", "Español", "🇪🇸"),
    ("ar", "العربية", "🇸🇦"),
    ("pl", "Polski", "🇵🇱"),
    ("pt", "Português", "🇧🇷"),
    ("ro", "Română", "🇷🇴"),
    ("fa", "فارسی", "🇮🇷"),
]


def build_welcome_blocks(user_name: str) -> list[dict]:
    """Block Kit message with a language picker sent as the first DM to a new member."""
    options = [
        {
            "text": {"type": "plain_text", "text": f"{flag} {name}", "emoji": True},
            "value": f"{code}|{name}",
        }
        for code, name, flag in LANGUAGE_OPTIONS
    ]
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Welcome, {user_name}!* 🙏\n\n"
                    "I'm *Threshold* — your guide to getting connected at "
                    "*Cornerstone Community Church*. I speak many languages and "
                    "I'm here to help you find your place — no referral needed.\n\n"
                    "*Which language do you prefer?*"
                ),
            },
        },
        {
            "type": "actions",
            "block_id": "language_picker",
            "elements": [
                {
                    "type": "static_select",
                    "action_id": "language_select",
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Choose your language…",
                        "emoji": True,
                    },
                    "options": options,
                }
            ],
        },
    ]


# ── Impact dashboard (Flow F / /threshold-impact) ────────────────────────────


def build_impact_blocks(summary: dict) -> list[dict]:
    """Block Kit summary for /threshold-impact."""
    langs = (
        ", ".join(summary["languages_served"]).upper()
        if summary["languages_served"]
        else "—"
    )

    avg = summary.get("avg_connection_seconds")
    if avg is not None:
        mins, secs = int(avg // 60), int(avg % 60)
        avg_str = f"{mins}m {secs}s"
    else:
        avg_str = "—"

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Threshold · Impact Dashboard",
                "emoji": True,
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*👋 Members welcomed*\n{summary['welcomed']}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*🌍 Languages served*\n{langs}",
                },
            ],
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*🤝 Matched to a group*\n{summary['matched']}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*📬 Intros posted*\n{summary['intro_made']}",
                },
            ],
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*📢 Digests sent*\n{summary['digest_sent']}",
                },
                {
                    "type": "mrkdwn",
                    "text": "*❌ Referrals needed*\n0 ✅",
                },
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*⏱️ Avg. time to first connection:* {avg_str}",
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "_Threshold — lowering barriers. Zero referrals needed._",
                }
            ],
        },
    ]


# ── Digest header block ──────────────────────────────────────────────────────


def build_digest_header_block(language_name: str) -> dict:
    """Header block prepended to a translated digest DM."""
    return {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"*📢 Church Announcements — {language_name}*\n"
                "Here's what's happening at Cornerstone this week:"
            ),
        },
    }
