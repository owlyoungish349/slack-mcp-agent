# Threshold — Engineering and Deployment Handover

Last updated: 10 July 2026 (Europe/London)

## 1. Executive summary

Threshold is a multilingual Slack belonging agent for a synthetic church community,
Cornerstone Community Church. It welcomes newcomers, stores their preferred language,
searches a Slack-hosted group directory through the Slack MCP Server, renders interactive
group cards, and introduces a newcomer to a real contact in the selected group channel.
It also creates translated announcement digests and shows an impact dashboard.

The project is being prepared for the Slack Agent Builder Challenge, primarily as a
Slack Agent for Good. The strongest demo story is reducing language and referral barriers
for newcomers: a Spanish-speaking newcomer can go from a welcome DM to a real human
introduction without already knowing the right person.

The production-style Droplet deployment is healthy on the last committed revision,
`d094c35`. A newer Persian/translation/UI change set is complete and tested locally but
is **not committed, pushed, or deployed** because the resumed Codex environment mounted
`.git` read-only and blocked outbound SSH.

## 2. Canonical identities and infrastructure

- Repository: `owlyoungish349/slack-mcp-agent`
- Local workspace: `C:\Users\alire\Documents\GitHub\slack-mcp-agent`
- Current Slack app ID (keep this app): `A0BGHDR0NLA`
- Current developer sandbox org: `threshold-commons-26.enterprise.slack.com`
- DigitalOcean Droplet: `188.166.150.193`
- Droplet application checkout: `/opt/threshold/app`
- Droplet secrets file: `/opt/threshold/.env`
- Persistent Droplet data: `/opt/threshold/data`
- Docker container name: `threshold`
- Docker image alias: `threshold:latest`

There is an older Slack app, `threshold-agent`, with app ID `A0BDRQ01S79`. It is the
probable source of duplicate `/threshold-welcome`, `/threshold-digest`, and
`/threshold-impact` suggestions. Do not delete the current `A0BGHDR0NLA` app.

## 3. Secret handling

Do not print or commit any token values.

The local `.env` is gitignored and Docker-ignored. The Droplet copy is stored outside the
repository at `/opt/threshold/.env`, owned by root with mode `600`. The configured variable
names include:

- `SLACK_BOT_TOKEN`
- `SLACK_APP_TOKEN`
- `SLACK_SIGNING_SECRET`
- `SLACK_USER_TOKEN`
- `GOOGLE_API_KEY`
- `GEMINI_API_KEY`
- `GITHUB_MODELS_TOKEN`

The GitHub token is used only as a tertiary GitHub Models fallback and needs `models:read`.
Do not replace the external Droplet `.env` during deployment.

## 4. Architecture and important behavior

The application uses Python, Slack Bolt, Pydantic AI, Slack Socket Mode, the Slack MCP
Server, Gemini, GitHub Models, SQLite, and Docker.

Main flow:

1. Slack events/actions/commands enter through Bolt listeners in `listeners/`.
2. User language and impact data are stored in SQLite through `store/user_store.py`.
3. The Pydantic AI agent in `agent/agent.py` uses Slack MCP for group searches,
   announcement reads, and the product's MCP-centered interactions.
4. Group cards are rendered with Block Kit and an `accept_intro` button.
5. The intro action deterministically calls Slack MCP to post the introduction, then logs
   impact only after the MCP call succeeds.
6. SQLite is written under `/data` in the container, bind-mounted to
   `/opt/threshold/data` on the Droplet.

See `docs/architecture.mmd`, `docs/architecture.png`, and `DEMO.md` for the visual design
and demo script.

## 5. Key engineering decisions and rationale

### Socket Mode and the operator user token

Socket Mode was chosen so the hackathon deployment does not require a public request URL.
In this mode, Bolt does not receive a per-user OAuth token. `listeners/utils.py` therefore
falls back to `SLACK_USER_TOKEN`, which belongs to the operator account.

Consequences:

- The operator account must be a member of `#announcements` and every destination group
  channel that MCP needs to read or post in.
- Newcomers do **not** need to join a group channel before asking for a match.
- The operator-channel membership is a service-setup requirement, not a newcomer
  prerequisite.
- This is suitable for the single-workspace hackathon deployment. A multi-workspace
  Marketplace product should replace it with per-installation OAuth token storage.

### Deterministic introduction posting

Originally the model was asked to post an introduction and log the result. This caused a
false-positive impact event when MCP failed with `not_in_channel`. The button handler now
resolves the channel, calls the MCP `slack_send_message` tool directly, and records
`intro_made` only after success. This makes the dashboard trustworthy.

### Unique-person impact metrics

Repeated demos by one person had inflated `welcomed` and `matched`. Those two metrics now
count distinct user IDs. `intro_made` and `digest_sent` remain action counts because each
successful delivery is a real outcome. Existing event history is retained; only the
aggregation changed.

### Model resilience

The model chain is:

1. `gemini-2.5-flash`
2. `gemini-3.1-flash-lite`
3. GitHub Models `openai/gpt-4.1` when `GITHUB_MODELS_TOKEN` is available
4. Optional Anthropic/OpenAI providers when their environment variables are configured

Transient 429/5xx/high-demand errors are retried with exponential backoff. Both the Gemini
fallback and GitHub Models fallback were deliberately forced and verified during setup.
GitHub Models is a useful hackathon backup, not an unlimited production tier.

### Translation is on demand

The pending translation feature deliberately does not auto-translate every workspace
message. Automatic translation would create noise, privacy concerns, and unnecessary model
usage. Instead, a user explicitly chooses **Translate text** from App Home or
**Translate with Threshold** from a message menu. The translated result is delivered
privately in the user's Threshold DM.

The translator preserves names, links, Slack mentions, formatting, and meaning. It follows
the existing product constraint not to translate scripture or liturgical text.

### Product name and command surface

Keep the name **Threshold** for the deadline. It is distinctive and supports the core story
of helping someone cross from isolation into belonging. Recommended tagline:

> Threshold — your open door to community.

Do not rename all slash commands immediately before submission. They are operator tools;
newcomers should use conversation, cards, App Home buttons, and shortcuts instead of
memorizing commands.

## 6. Work already committed and deployed

Important commits, newest first:

- `d094c35` — App Home recognizes the configured Socket Mode user token and shows MCP as connected
- `46783db` — unique-person impact metrics for welcomed/matched
- `bab002f` — impact command responds ephemerally outside bot-member channels
- `ded7c02` — use an actually available Gemini 3.1 fallback model
- `3f61cab` — resilient multi-model fallback chain
- `56bad4a` — log introductions only after direct MCP post succeeds
- `c5e574f` — resolve escaped/raw users and `me` in `/threshold-welcome`
- `0422e2e` — seed canonical workspace content without treating Slack join events as content
- `a726d24` — remove invalid empty slash-command usage hints
- `a586fcb` — Docker/DigitalOcean deployment safety and persistent storage documentation

The live container at the time of this handover runs `d094c35` and has an active Socket Mode
session. App Home was visibly verified with a green **Slack MCP Server is connected** status.

## 7. Verified end-to-end behavior

The following flows have worked in the sandbox:

- `/threshold-welcome me` sends a welcome DM.
- Spanish can be selected and is persisted.
- A Spanish request for Sunday café volunteering causes a real Slack MCP search and a
  localized Café Volunteering card.
- Clicking the introduction button posts a real message in `#cafe-volunteers`, mentioning
  the newcomer and naming `@james-t`.
- The Spanish success confirmation appears only after the MCP post succeeds.
- `/threshold-impact` responds outside channels the bot has joined.
- The Droplet survives reboot, reconnects Socket Mode, and retains the SQLite database.
- The database checksum was identical before and after the reboot durability test.
- Forced Gemini and GitHub Models fallbacks both worked.

The most recently inspected live summary was approximately one unique welcomed member, one
unique matched member, one successful introduction, one digest event, and Spanish served.
Action counts can increase during later UI tests.

## 8. Pending, uncommitted feature set

The working tree currently contains a complete pending feature set:

- Persian (`fa`, `فارسی`) in the welcome language selector
- Persian greeting after selection
- Persian introduction-success confirmation
- Persian included in the agent's supported-language prompt and App Home language list
- A **Start chatting** primary button on App Home
- A **Translate text** button on App Home
- An on-demand translation modal with language selection
- A `Translate with Threshold` message shortcut in `manifest.json`
- A dedicated translation agent that uses the same resilient model chain
- Private DM delivery of translation results
- Unit tests for Persian, App Home actions, modal defaults, validation, translation delivery,
  and the Start chatting action

Files changed/added:

- `agent/agent.py`
- `agent/translation.py` (new)
- `listeners/actions/__init__.py`
- `listeners/actions/accept_intro.py`
- `listeners/actions/language_select.py`
- `listeners/actions/start_conversation.py` (new)
- `listeners/actions/translation.py` (new)
- `listeners/views/app_home_builder.py`
- `listeners/views/threshold_blocks.py`
- `manifest.json`
- `tests/test_home_actions.py` (new)
- `tests/test_translation.py` (new)
- `tests/test_view_builders.py`

Validation completed:

- Ruff: all checks passed
- Pytest: `32 passed`, one third-party Google GenAI deprecation warning
- Python compilation: passed
- `manifest.json`: valid JSON
- `git diff --check`: clean except normal Windows LF/CRLF notices

The first pytest rerun failed only because the resumed sandbox could not access the default
Windows temp folder. It passed using:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-temp-resume
```

## 9. Why the pending work is not deployed

The resumed Codex environment has these restrictions:

- `.git` is read-only, so `git add`/`git commit` fail while creating `.git/index.lock`.
- Outbound SSH is blocked, so `ssh root@188.166.150.193` returns permission denied.

No source changes were lost. They remain in the working tree. Claude Code should continue
from this exact state rather than recreating the feature.

## 10. Exact continuation steps for Claude Code

First inspect and revalidate:

```powershell
git status --short
.\.venv\Scripts\python.exe -m ruff check agent listeners tests
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=.pytest-temp-resume
.\.venv\Scripts\python.exe -c "import json, pathlib; json.loads(pathlib.Path('manifest.json').read_text(encoding='utf-8')); print('manifest json ok')"
git diff --check
```

Commit and push only the listed Threshold files; preserve unrelated user work:

```powershell
git add HANDOVER.md agent/agent.py agent/translation.py listeners/actions/__init__.py listeners/actions/accept_intro.py listeners/actions/language_select.py listeners/actions/start_conversation.py listeners/actions/translation.py listeners/views/app_home_builder.py listeners/views/threshold_blocks.py manifest.json tests/test_home_actions.py tests/test_translation.py tests/test_view_builders.py
git commit -m "feat: add Persian and on-demand translation"
git push origin main
git rev-parse --short HEAD
```

Then deploy using the actual new short commit hash in place of `<hash>`:

```bash
ssh root@188.166.150.193
cd /opt/threshold/app
git pull --ff-only origin main
git rev-parse --short HEAD
docker build -t threshold:<hash> -t threshold:latest .
docker rm -f threshold
docker run -d \
  --name threshold \
  --restart=always \
  --env-file /opt/threshold/.env \
  -v /opt/threshold/data:/data \
  threshold:latest
sleep 8
docker ps --filter name=threshold
docker logs --tail 50 threshold
```

Expected log lines include a new Socket Mode session and `Bolt app is running!`. Confirm the
persistent summary without printing secrets:

```bash
docker exec threshold python -c 'from store.user_store import get_impact_summary; print(get_impact_summary())'
```

## 11. Slack configuration still required for the message shortcut

Deploying the code does not update Slack's app configuration. After deployment, update the
current app `A0BGHDR0NLA` through its App Manifest, or create this message shortcut manually
under **Interactivity & Shortcuts**:

- Name: `Translate with Threshold`
- Type: `Message`
- Callback ID: `translate_with_threshold`
- Description: `Translate this message into your chosen language`

The repository's `manifest.json` already contains the correct shortcut declaration. Socket
Mode requires no public interactivity request URL.

## 12. Resolve duplicate slash commands before further testing

The code and current manifest contain only one declaration of each command. Duplicate Slack
autocomplete entries almost certainly come from two installed apps.

Recommended cleanup:

1. Open the sandbox's **Manage apps** page.
2. Find both `Threshold` and the older `threshold-agent` if both appear.
3. Keep the app with ID `A0BGHDR0NLA`.
4. Uninstall the older app with ID `A0BDRQ01S79` from this sandbox.
5. In the current app dashboard, open **Slash Commands** and verify exactly one entry for:
   `/threshold-welcome`, `/threshold-digest`, and `/threshold-impact`.
6. Test autocomplete again. Delete the old developer app only after confirming the current
   app still works.

This also explains why an old impact dashboard could appear even after the Droplet had the
new aggregation: Slack could route the identically named slash command to the old app.

## 13. Post-deployment UI test checklist

1. Open **Apps → Threshold → Home**.
2. Confirm the green MCP status, Persian in the language list, and both quick-action buttons.
3. Click **Start chatting** and confirm a fresh DM with the language picker.
4. Select `🇮🇷 فارسی` and confirm the Persian greeting.
5. Send `می‌خواهم روزهای یکشنبه داوطلب شوم.` and confirm a Persian match card.
6. Click **Translate text**, paste `Welcome to our community`, select Persian, and confirm a
   private translation DM.
7. On any ordinary Slack message, choose **More actions → Translate with Threshold** and
   confirm the modal is pre-filled with that message.
8. Run all three slash commands once after removing the old app.
9. Recheck `/threshold-impact`; unique-person counts should not inflate from repeat welcome
   and matching tests.

## 14. Suggested prompts for product testing and the demo

English:

- `I just moved here and would like to meet people. What group would suit me?`
- `I can help on Sunday mornings but my English is limited.`
- `Are there any groups for families with children?`
- `What is happening at Cornerstone this week?`

Spanish:

- `Me gustaría ayudar en el café los domingos.`
- `Busco un grupo para familias con niños.`
- `¿Qué actividades hay esta semana?`

Persian:

- `من تازه به اینجا آمده‌ام و دنبال یک گروه دوستانه هستم.`
- `می‌خواهم روزهای یکشنبه داوطلب شوم.`
- `این هفته در Cornerstone چه برنامه‌هایی برگزار می‌شود؟`

Arabic:

- `أنا جديد هنا وأبحث عن مجموعة تتحدث العربية.`
- `هل توجد فرص للتطوع يوم الأحد؟`

Conversation-memory test:

1. Ask for a family group.
2. Reply in the same thread: `Which day does it meet?`
3. Reply again: `Please introduce me.`

## 15. Known limitations and follow-up ideas

- The operator token architecture is single-workspace and requires channel membership.
- The Start chatting button sends a DM but cannot force Slack to change the visible tab.
- Translation is intentionally on demand and delivered by DM.
- The impact dashboard displays referrals needed as zero; there is not yet a complete
  referral-escalation workflow behind that metric.
- The digest command currently loops synchronously through opted-in users; a larger
  production deployment should queue jobs and enforce concurrency/rate limits.
- A useful next operator feature is `/threshold-status`, checking operator membership in
  `#announcements` and all group channels before a demo.
- A high-impact newcomer feature is a contact-side **I'll help** button followed by a private
  confirmation to the newcomer.
- A scheduled follow-up after an introduction would measure whether the connection actually
  happened.
- For a Marketplace/multi-workspace version, add OAuth installation storage, token rotation,
  tenant-aware databases, privacy documentation, deletion/export controls, and production
  workspace testing.

## 16. Demo priorities

If time is limited, prioritize this sequence:

1. Green MCP App Home.
2. Spanish or Persian welcome selection.
3. Natural-language request.
4. MCP-backed localized group card.
5. Button-driven real introduction in the group channel.
6. On-demand translation.
7. Accurate impact dashboard.

That sequence demonstrates the social problem, multilingual UX, Slack-native interaction,
real workspace grounding, human handoff, and measurable outcome in under three minutes.
