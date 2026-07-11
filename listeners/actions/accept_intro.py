"""Flow B — handle the "Introduce me" button on a group match card.

The button posts a deterministic warm intro through the Slack MCP Server,
then records impact only after MCP confirms that the post succeeded.
"""

import asyncio
import json
from logging import Logger

from pydantic_ai.mcp import MCPServerStreamableHTTP
from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from listeners.utils import get_user_token
from store import user_store

_SLACK_MCP_URL = "https://mcp.slack.com/mcp"

_CONFIRMATIONS = {
    "en": "Done! I introduced you in #{channel} — head over and say hello.",
    "es": "¡Listo! Te presenté en #{channel}; pásate por allí para saludar.",
    "ar": "تم! عرّفت بك في #{channel} — توجّه إلى هناك وألقِ التحية.",
    "pl": "Gotowe! Przedstawiłem Cię na #{channel} — zajrzyj tam i przywitaj się.",
    "pt": "Pronto! Apresentei você em #{channel} — passe por lá para dizer olá.",
    "ro": "Gata! Te-am prezentat în #{channel} — intră acolo și salută-i.",
    "fa": "انجام شد! شما را در #{channel} معرفی کردم — سری بزنید و سلام کنید.",
}

_INTRODUCING = {
    "en": "🤝 Introducing you to *{group}*…",
    "es": "🤝 Presentándote a *{group}*…",
    "ar": "🤝 جارٍ تقديمك إلى *{group}*…",
    "pl": "🤝 Przedstawiam Cię grupie *{group}*…",
    "pt": "🤝 Apresentando você a *{group}*…",
    "ro": "🤝 Te prezint grupului *{group}*…",
    "fa": "🤝 در حال معرفی شما به *{group}*…",
}

_FAILURES = {
    "en": "⚠️ I couldn't post the introduction just now — please try the button again in a moment.",
    "es": "⚠️ No pude publicar la presentación ahora mismo. Vuelve a intentarlo en un momento.",
    "ar": "⚠️ لم أتمكن من نشر التعريف الآن. يُرجى المحاولة مرة أخرى بعد قليل.",
    "pl": "⚠️ Nie udało mi się teraz opublikować przedstawienia. Spróbuj ponownie za chwilę.",
    "pt": "⚠️ Não consegui publicar a apresentação agora. Tente novamente em instantes.",
    "ro": "⚠️ Nu am putut publica prezentarea acum. Încearcă din nou peste puțin timp.",
    "fa": "⚠️ فعلاً نتوانستم معرفی را ارسال کنم. لطفاً کمی بعد دوباره تلاش کنید.",
}


def _find_channel_id(client: WebClient, channel_name: str) -> str | None:
    """Resolve a public channel name to its Slack channel ID."""
    cursor = None
    while True:
        response = client.conversations_list(
            types="public_channel",
            exclude_archived=True,
            limit=200,
            cursor=cursor,
        )
        for channel in response.get("channels", []):
            if channel.get("name") == channel_name:
                return channel.get("id")
        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            return None


async def _post_intro_via_mcp(user_token: str, channel_id: str, message: str) -> None:
    server = MCPServerStreamableHTTP(
        _SLACK_MCP_URL,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    await server.direct_call_tool(
        "slack_send_message",
        {"channel_id": channel_id, "message": message},
    )


def _build_intro_message(user_id: str, group: str, contact: str) -> str:
    contact_label = contact if contact.startswith("@") else f"@{contact}"
    return (
        f"Hi everyone! <@{user_id}> is interested in joining *{group}*. "
        f"{contact_label}, could you help them get connected? Welcome!"
    )


def _confirmation(language_code: str, channel: str) -> str:
    template = _CONFIRMATIONS.get(language_code, _CONFIRMATIONS["en"])
    return template.format(channel=channel)


def _localized(mapping: dict[str, str], language_code: str, **values: str) -> str:
    template = mapping.get(language_code, mapping["en"])
    return template.format(**values)


def handle_accept_intro(
    ack: Ack,
    body: dict,
    client: WebClient,
    context: BoltContext,
    logger: Logger,
) -> None:
    ack()

    try:
        payload = json.loads(body["actions"][0]["value"])
        user_id = body["user"]["id"]
        channel_id = body["container"]["channel_id"]
        thread_ts = body.get("message", {}).get("thread_ts")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.exception("Malformed accept_intro payload: %s", e)
        return

    lang_code, _lang_name = user_store.get_language(user_id)

    # Immediate feedback while the agent works (~a few seconds).
    try:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            thread_ts=thread_ts,
            text=_localized(_INTRODUCING, lang_code, group=payload["group"]),
        )
    except SlackApiError:
        pass  # ephemeral feedback is best-effort

    try:
        user_token = get_user_token(context)
        if not user_token:
            raise RuntimeError("No Slack user token available for MCP")
        destination_id = _find_channel_id(client, payload["channel"])
        if not destination_id:
            raise RuntimeError(f"Could not resolve #{payload['channel']}")

        intro_message = _build_intro_message(
            user_id, payload["group"], payload["contact"]
        )
        asyncio.run(_post_intro_via_mcp(user_token, destination_id, intro_message))

        user_store.log_event(
            "intro_made",
            user_id,
            lang_code,
            metadata={"detail": payload["group"]},
        )
        confirmation = _confirmation(lang_code, payload["channel"])
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=confirmation,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"✅ {confirmation}"},
                }
            ],
        )
        logger.info(
            "Intro posted for %s -> %s (#%s)",
            user_id,
            payload["group"],
            payload["channel"],
        )
    except Exception as e:
        logger.exception("Intro post failed for %s: %s", user_id, e)
        try:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                thread_ts=thread_ts,
                text=_localized(_FAILURES, lang_code),
            )
        except SlackApiError:
            pass
