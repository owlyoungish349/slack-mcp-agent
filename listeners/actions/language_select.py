"""Handle the language picker action from the welcome DM (Flow A)."""

from logging import Logger

from slack_bolt import Ack, BoltContext
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from store import user_store

# Greeting sent in each language after the user selects.
# The agent then continues the conversation in that language.
_GREETINGS: dict[str, str] = {
    "en": (
        "Great — I'll speak English with you! 🙏\n\n"
        "What brings you to Cornerstone? I can help you find life groups, "
        "English classes, volunteering, or just a friendly place to start. "
        "What are you looking for?"
    ),
    "es": (
        "¡Perfecto — hablaré contigo en español! 🙏\n\n"
        "¿Qué te trae a Cornerstone? Puedo ayudarte a encontrar grupos de vida, "
        "clases de inglés, voluntariado o simplemente un lugar amigable para empezar. "
        "¿Qué estás buscando?"
    ),
    "ar": (
        "رائع — سأتحدث معك باللغة العربية! 🙏\n\n"
        "ما الذي يجلبك إلى Cornerstone؟ يمكنني مساعدتك في إيجاد مجموعات الحياة، "
        "دروس اللغة الإنجليزية، العمل التطوعي، أو مجرد مكان ودود للبدء. "
        "ما الذي تبحث عنه؟"
    ),
    "pl": (
        "Świetnie — będę rozmawiać z Tobą po polsku! 🙏\n\n"
        "Co Cię przyciągnęło do Cornerstone? Mogę pomóc Ci znaleźć grupy życiowe, "
        "kursy angielskiego, wolontariat lub po prostu przyjazne miejsce na start. "
        "Czego szukasz?"
    ),
    "pt": (
        "Ótimo — vou falar português com você! 🙏\n\n"
        "O que te trouxe à Cornerstone? Posso ajudar a encontrar grupos de vida, "
        "aulas de inglês, voluntariado ou simplesmente um lugar amigável para começar. "
        "O que você está procurando?"
    ),
    "ro": (
        "Grozav — voi vorbi română cu tine! 🙏\n\n"
        "Ce te-a adus la Cornerstone? Te pot ajuta să găsești grupuri de viață, "
        "cursuri de engleză, voluntariat sau pur și simplu un loc prietenos pentru început. "
        "Ce cauți?"
    ),
}


def handle_language_select(
    ack: Ack,
    body: dict,
    client: WebClient,
    context: BoltContext,
    logger: Logger,
) -> None:
    ack()

    try:
        action = body["actions"][0]
        value = action["selected_option"]["value"]  # e.g. "es|Spanish"
        lang_code, lang_name = value.split("|", 1)

        user_id = body["user"]["id"]
        channel_id = body["container"]["channel_id"]
        message_ts = body["container"]["message_ts"]

        # Persist the preference
        user_store.set_language(user_id, lang_code, lang_name)
        user_store.log_event("language_set", user_id, lang_code)

        # Replace the picker message with the greeting
        greeting = _GREETINGS.get(lang_code, _GREETINGS["en"])
        client.chat_update(
            channel=channel_id,
            ts=message_ts,
            text=greeting,
            blocks=[
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": greeting},
                }
            ],
        )

        logger.info("Language set to %s (%s) for user %s", lang_name, lang_code, user_id)

    except (SlackApiError, KeyError) as e:
        logger.exception("Failed to handle language_select: %s", e)
