from slack_bolt import App

from .accept_intro import handle_accept_intro
from .feedback_buttons import handle_feedback_button
from .group_message import (
    handle_group_message_submission,
    handle_open_group_message,
)
from .language_select import handle_language_select
from .start_conversation import handle_start_conversation
from .translation import (
    handle_open_translation,
    handle_translate_shortcut,
    handle_translation_submission,
)


def register(app: App):
    app.action("accept_intro")(handle_accept_intro)
    app.action("feedback")(handle_feedback_button)
    app.action("language_select")(handle_language_select)
    app.action("start_conversation")(handle_start_conversation)
    app.action("open_translation")(handle_open_translation)
    app.action("open_group_message")(handle_open_group_message)
    app.shortcut("translate_with_threshold")(handle_translate_shortcut)
    app.view("translate_text_submit")(handle_translation_submission)
    app.view("group_message_submit")(handle_group_message_submission)
