from slack_bolt import App

from .threshold_digest import handle_threshold_digest
from .threshold_impact import handle_threshold_impact
from .threshold_welcome import handle_threshold_welcome


def register(app: App) -> None:
    app.command("/threshold-welcome")(handle_threshold_welcome)
    app.command("/threshold-digest")(handle_threshold_digest)
    app.command("/threshold-impact")(handle_threshold_impact)
