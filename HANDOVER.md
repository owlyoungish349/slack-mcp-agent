# Threshold — Engineering and Deployment Handover

Last updated: 11 July 2026 (Europe/London)

## 1. Executive summary

Threshold is a multilingual Slack belonging agent for a synthetic church community,
Cornerstone Community Church. It welcomes newcomers, stores their preferred language,
searches a Slack-hosted group directory through the Slack MCP Server, renders interactive
group cards, and introduces a newcomer to a real contact in the selected group channel.
It also creates translated announcement digests, offers on-demand translation in both
directions, and shows an impact dashboard.

The project is being prepared for the Slack Agent Builder Challenge, primarily as a
Slack Agent for Good. The strongest demo story is reducing language and referral barriers
for newcomers: a Spanish- or Persian-speaking newcomer can go from a welcome DM to a real
human introduction without already knowing the right person, and can now also speak *to*
the group in their own language.

**Current state:** everything is committed, pushed, and deployed. The Droplet runs
revision `39136a3` with an active Socket Mode session. Two feature sets shipped since the
previous (10 July) handover:

1. `daa63de` — Persian language support and on-demand inbound translation
   (the set that was stuck uncommitted in the Codex environment).
2. `39136a3` — **Write to a group**: compose a message in any language from App Home and
   Threshold posts it in English to a chosen channel with attribution.

The duplicate slash-command problem from the previous handover has resolved (details in
§12). Remaining manual work is Slack-side verification only (§11, §13).

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
- Docker image alias: `threshold:latest` (also tagged per-commit, e.g. `threshold:39136a3`)

There is an older Slack developer app, `threshold-agent`, with app ID `A0BDRQ01S79`. It was
the suspected source of duplicate slash-command suggestions; the duplicates have since
disappeared (§12). If the old developer app still exists at api.slack.com, delete it only
after the final demo is confirmed working. Do not delete the current `A0BGHDR0NLA` app.

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
6. The **Write to a group** action (`listeners/actions/group_message.py`) follows the same
   deterministic pattern: translate to English, post via MCP `slack_send_message`, log
   `message_posted` only after success, then confirm privately in the user's language.
7. SQLite is written under `/data` in the container, bind-mounted to
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

The translation feature deliberately does not auto-translate every workspace message.
Automatic translation would create noise, privacy concerns, and unnecessary model usage.
Instead, a user explicitly chooses **Translate text** from App Home or **Translate with
Threshold** from a message menu. The translated result is delivered privately in the
user's Threshold DM.

The translator preserves names, links, Slack mentions, formatting, and meaning. It follows
the existing product constraint not to translate scripture or liturgical text.

### Write to a group — outbound translation (new, `39136a3`)

The inbound translator lets a newcomer *understand* the community privately. The operator
asked for the reverse: write in Persian (or any language) and have it delivered to a group
in English. Design decisions and reasoning:

- **Entry point is a third App Home button, "Write to a group",** opening a modal with a
  multiline message input and a channel picker. This keeps the deterministic, demoable UI
  pattern rather than relying on free-form agent conversation.
- **The target language is fixed to English.** Destination groups operate in English; a
  target-language selector would add a decision the newcomer does not need to make. The
  source language is whatever they type — no selector needed there either, the translator
  handles it.
- **The channel picker is Slack's native `channels_select` element** (public channels).
  This avoids an MCP round trip to enumerate channels and returns a channel ID directly,
  so no name-to-ID resolution is needed.
- **Posting reuses the deterministic MCP pattern from `accept_intro.py`:** direct
  `slack_send_message` call with the operator token, and a new `message_posted` event is
  logged **only after** the MCP call succeeds — consistent with the trustworthy-dashboard
  principle. On failure the user gets an error DM and nothing is logged.
- **Attribution is explicit.** The channel post reads
  `🌐 <@user> says (translated by Threshold): <english text>` so the group knows who is
  speaking and that Threshold translated on their behalf.
- **Confirmation is private and localized** in all seven supported languages, mirroring
  the intro-confirmation pattern.
- **`message_posted` is stored in SQLite but intentionally not yet surfaced on the impact
  dashboard.** The dashboard schema was left unchanged this close to the deadline; the
  data is being collected for a later metric.
- **No manifest change was needed.** App Home buttons and modals are not app-config
  surface, so this feature deployed with code only.

### Product name and command surface

Keep the name **Threshold** for the deadline. It is distinctive and supports the core story
of helping someone cross from isolation into belonging. Recommended tagline:

> Threshold — your open door to community.

Do not rename all slash commands immediately before submission. They are operator tools;
newcomers should use conversation, cards, App Home buttons, and shortcuts instead of
memorizing commands.

## 6. Work committed and deployed

Important commits, newest first:

- `39136a3` — write to a group in your own language (App Home button, modal, deterministic
  MCP post with attribution, localized confirmations, 4 new tests)
- `daa63de` — Persian and on-demand translation (the previously pending set; also added
  this HANDOVER.md to the repository)
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

The live container runs `39136a3`. Both deploys on 11 July were verified with a fresh
Socket Mode session and `Bolt app is running!` in the logs. The local working tree is
clean and identical to `origin/main`.

## 7. Verified end-to-end behavior

Verified in the sandbox before this session:

- `/threshold-welcome me` sends a welcome DM.
- Spanish can be selected and is persisted.
- A Spanish request for Sunday café volunteering causes a real Slack MCP search and a
  localized Café Volunteering card.
- Clicking the introduction button posts a real message in `#cafe-volunteers`, mentioning
  the newcomer and naming `@james-t`.
- The Spanish success confirmation appears only after the MCP post succeeds.
- `/threshold-impact` responds outside channels the bot has joined.
- The Droplet survives reboot, reconnects Socket Mode, and retains the SQLite database.
- Forced Gemini and GitHub Models fallbacks both worked.

Verified during the 11 July session:

- Both container replacements (`daa63de`, then `39136a3`) came up with new Socket Mode
  sessions and running Bolt apps.
- The SQLite impact data survived the `daa63de` container replacement. Summary read from
  the live container after that deploy: 1 unique welcomed, 1 unique matched, 2 intros
  made, 2 digests sent, Spanish served, average time-to-connection ~60 minutes.
- Local validation for both commits: ruff clean, full pytest suite passing
  (32 tests at `daa63de`, 36 at `39136a3`), `manifest.json` valid, `git diff --check`
  clean.

**Not yet verified:** the Persian UI flows, the translation modals, and the new Write to a
group flow have been deployed but not yet exercised in the Slack client. The §13 checklist
covers them.

## 8. What happened in the 11 July Claude Code session

1. **Recovered the stuck Codex work.** Revalidated the pending working tree (ruff, pytest,
   manifest, diff check), committed the 14 listed files as `daa63de`, pushed, and deployed
   to the Droplet. Confirmed the persisted impact summary from inside the live container.
2. **Walked the operator through the Slack-side steps** (message shortcut, duplicate-app
   cleanup, UI checklist).
3. **Duplicate slash commands resolved** (§12).
4. **Built, tested, committed (`39136a3`), pushed, and deployed the Write to a group
   feature** at the operator's request ("I want to write in for example Persian and it
   would translate it back in English and send it to the group").

Files changed in `39136a3`:

- `listeners/actions/group_message.py` (new — modal builder, open handler, submission
  handler, MCP post helper, localized confirmations)
- `listeners/actions/__init__.py` (registers `open_group_message` action and
  `group_message_submit` view)
- `listeners/views/app_home_builder.py` (third quick-action button)
- `tests/test_group_message.py` (new — modal shape, happy path with a Persian message,
  empty-text rejection, MCP-failure path)
- `tests/test_view_builders.py` (asserts the new button is present)

Testing note: in `tests/test_group_message.py`, `_post_message_via_mcp` is patched with
`new_callable=Mock` (not the default `AsyncMock`) because `asyncio.run` is also mocked —
an `AsyncMock`'s `side_effect` only fires when awaited, so the failure path instead raises
from the mocked `asyncio.run`.

## 9. Environment notes for the next session

- **The repository state is fully on `origin/main`.** A Claude web UI session cloning from
  GitHub gets everything; there is no pending local-only work.
- **A web session cannot deploy.** The Droplet is reachable only via SSH key from the
  operator's machine. Code and tests can be developed and pushed from anywhere; the
  operator (or a local Claude Code session) must run the §10 runbook to deploy.
- **Claude Code required explicit per-deploy operator approval** for SSH to the Droplet;
  expect the same in future local sessions.
- **Windows quirk:** `.pytest-temp-resume/` in the repo root is a permission-locked
  leftover from the old Codex sandbox. It cannot be deleted without an elevated shell
  (`takeown` + `icacls`). It is untracked and harmless apart from a `git status` warning.
  Do not use it as pytest's basetemp; pass any fresh writable directory instead:

  ```powershell
  .\.venv\Scripts\python.exe -m ruff check agent listeners tests
  .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp=<fresh-dir>
  ```

- **Windows PowerShell 5.1 quirk:** multi-line commit messages via here-strings got
  mangled when chained with other commands; `git commit -F <message-file>` is reliable.

## 10. Deployment runbook

From the Droplet, using the short hash of the commit being deployed:

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

Expected log lines include a new Socket Mode session and `Bolt app is running!`. Confirm
the persistent summary without printing secrets:

```bash
docker exec threshold python -c 'from store.user_store import get_impact_summary; print(get_impact_summary())'
```

Do not replace the external `/opt/threshold/.env` during deployment.

## 11. Slack configuration — verify the message shortcut

Deploying code does not update Slack's app configuration. The **Translate with Threshold**
message shortcut must exist on app `A0BGHDR0NLA`, added either through the App Manifest
editor or manually under **Interactivity & Shortcuts**:

- Name: `Translate with Threshold`
- Type: `Message`
- Callback ID: `translate_with_threshold`
- Description: `Translate this message into your chosen language`

The repository's `manifest.json` contains the correct declaration. The operator was given
the exact steps on 11 July but completion has **not been confirmed** — verify by opening
**More actions** on any message and looking for the shortcut. Socket Mode requires no
public interactivity request URL. No further Slack configuration is needed for Write to a
group (App Home buttons and modals are code-only).

## 12. Duplicate slash commands — resolved

The previous handover predicted the duplicates came from the older `threshold-agent` app
(`A0BDRQ01S79`) being installed alongside the current app. On 11 July the operator found
only **one** Threshold app in Manage apps and the duplicate autocomplete entries had
disappeared on their own — most likely a combination of stale client cache and the old
app's state settling; the root cause was never definitively pinned down.

Remaining cleanup: check https://api.slack.com/apps for the old `A0BDRQ01S79` developer
app. If it still exists, delete it — but only after the final demo is confirmed working on
the current app. If duplicates ever reappear, that old app is the first suspect.

## 13. Post-deployment UI test checklist

1. Open **Apps → Threshold → Home** (revisiting the tab re-renders the view).
2. Confirm the green MCP status, Persian in the language list, and **three** quick-action
   buttons: Start chatting, Translate text, Write to a group.
3. Click **Start chatting** and confirm a fresh DM with the language picker.
4. Select `🇮🇷 فارسی` and confirm the Persian greeting.
5. Send `می‌خواهم روزهای یکشنبه داوطلب شوم.` and confirm a Persian match card.
6. Click **Translate text**, paste `Welcome to our community`, select Persian, and confirm
   a private translation DM.
7. On any ordinary Slack message, choose **More actions → Translate with Threshold** and
   confirm the modal is pre-filled with that message (requires §11).
8. Click **Write to a group**, type `می‌خواهم روزهای یکشنبه در کافه کمک کنم`, pick
   `#cafe-volunteers`, and Send. Confirm an English post appears in the channel as
   `🌐 @you says (translated by Threshold): …` and a Persian confirmation arrives in your
   Threshold DM. If it fails, first check that the operator account is a member of the
   destination channel.
9. Run all three slash commands once and confirm single autocomplete entries.
10. Recheck `/threshold-impact`; unique-person counts should not inflate from repeat
    welcome and matching tests. After Persian tests, `languages served` should include FA.

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

Persian, for the Write to a group modal:

- `می‌خواهم روزهای یکشنبه در کافه کمک کنم.`

Arabic:

- `أنا جديد هنا وأبحث عن مجموعة تتحدث العربية.`
- `هل توجد فرص للتطوع يوم الأحد؟`

Conversation-memory test:

1. Ask for a family group.
2. Reply in the same thread: `Which day does it meet?`
3. Reply again: `Please introduce me.`

## 15. Known limitations and follow-up ideas

- The operator token architecture is single-workspace and requires operator membership in
  every destination channel (intros **and** Write to a group posts).
- Write to a group only offers public channels (native `channels_select`), fixes the
  target language to English, and its modal chrome is English-only; the message content
  can be any language.
- `message_posted` events are stored but not yet shown on the impact dashboard.
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
6. On-demand translation — inbound (Translate text) and outbound (Write to a group).
7. Accurate impact dashboard.

That sequence demonstrates the social problem, multilingual UX, Slack-native interaction,
real workspace grounding, human handoff, two-way language access, and measurable outcome
in under three minutes.
