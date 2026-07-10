from slack_bolt import App

from .accept_intro import handle_accept_intro
from .feedback_buttons import handle_feedback_button
from .language_select import handle_language_select


def register(app: App):
    app.action("accept_intro")(handle_accept_intro)
    app.action("feedback")(handle_feedback_button)
    app.action("language_select")(handle_language_select)
