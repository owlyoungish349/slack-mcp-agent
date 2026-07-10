"""Flow B — handle the "Introduce me" button on a group match card.

The button click hands off to the agent, which posts a warm intro in the
group's channel via the Slack MCP Server (the required-tech path), tags the
newcomer, names the group contact, and logs the intro_made impact event.
"""

import json
from logging import Logger

from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from agent import AgentDeps, run_agent
from listeners.utils import get_user_token
from store import user_store

_INTRO_PROMPT = """\
The newcomer <@{user_id}> tapped the button to be introduced to the group \
"{group}" (channel: #{channel}, contact person: {contact}).

Do the following, in order:
1. Use the Slack MCP Server to post a short, warm intro message IN the #{channel} \
channel. The message must be in English (so the contact can read it), must mention \
the newcomer as <@{user_id}>, must name the contact ({contact}), and should say the \
newcomer is interested in joining. 2–3 sentences, friendly, no fluff.
2. Log the impact event: log_impact_event(event_type='intro_made', \
user_id='{user_id}', detail='{group}').
3. Reply to the newcomer in {language_name} with ONE short sentence confirming the \
introduction was posted in #{channel} and encouraging them to say hi there.

CRITICAL: step 1 MUST go through the Slack MCP Server tools, not any local tool.
"""


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
        message_ts = body["container"]["message_ts"]
        thread_ts = body.get("message", {}).get("thread_ts")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.exception("Malformed accept_intro payload: %s", e)
        return

    _lang_code, lang_name = user_store.get_language(user_id)

    # Immediate feedback while the agent works (~a few seconds).
    try:
        client.chat_postEphemeral(
            channel=channel_id,
            user=user_id,
            thread_ts=thread_ts,
            text=f"🤝 Introducing you to *{payload['group']}*…",
        )
    except SlackApiError:
        pass  # ephemeral feedback is best-effort

    deps = AgentDeps(
        client=client,
        user_id=user_id,
        channel_id=channel_id,
        thread_ts=thread_ts or "",
        message_ts=message_ts,
        user_token=get_user_token(context),
    )
    prompt = _INTRO_PROMPT.format(
        user_id=user_id,
        group=payload["group"],
        channel=payload["channel"],
        contact=payload["contact"],
        language_name=lang_name,
    )

    try:
        result = run_agent(prompt, deps)
        client.chat_postMessage(
            channel=channel_id,
            thread_ts=thread_ts,
            text=result.output,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"✅ {result.output}"},
                }
            ],
        )
        logger.info(
            "Intro posted for %s -> %s (#%s)", user_id, payload["group"], payload["channel"]
        )
    except Exception as e:
        logger.exception("Intro post failed for %s: %s", user_id, e)
        try:
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                thread_ts=thread_ts,
                text="⚠️ I couldn't post the introduction just now — please try the button again in a moment.",
            )
        except SlackApiError:
            pass
