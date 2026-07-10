# Threshold — Demo Runbook

The exact message-by-message sequence for recording the demo video and for
rehearsals. Follow it verbatim; every line has been verified end-to-end.

## Before every take

1. Reset the workspace to the known-good state:
   ```sh
   python -m seed.reset_workspace
   ```
2. In Slack (as each persona), delete the DM history with **Threshold** so the
   welcome flow starts clean (hover message → ⋯ → Delete; or start a fresh take
   with a persona that has never talked to the bot).
3. Confirm the agent is up: the droplet container must be running
   (`ssh root@<droplet-ip> 'docker ps'` shows `threshold`). The bot's presence
   dot in Slack should be green.
4. `/threshold-impact` should show zeros (fresh reset) — the demo makes the
   numbers tick up live, which is the closing beat.

## Cast (synthetic personas — no real people)

| Persona | Role | Language |
|---|---|---|
| **Lucía** (second account) | The newcomer we follow | Spanish |
| **james-t** | Café volunteering contact (named in `#groups-directory`) | English |
| Operator main account | Runs slash commands, plays "admin" | English |

Channels used on camera: DM with Threshold, `#cafe-volunteers`, `#welcome`.

## The 60-second opening (the emotional beat)

**Scene: Lucía, who speaks little English, joins the church Slack.**

| # | Actor | Action / exact message | What you'll see |
|---|---|---|---|
| 1 | Lucía | Join `#welcome` (or operator runs `/threshold-welcome @lucia`) | Threshold DMs Lucía a welcome card with a language picker |
| 2 | Lucía | Pick **🇪🇸 Español** from the dropdown | Picker is replaced by a Spanish greeting asking what she's looking for |
| 3 | Lucía | Type: `Me gustaría ayudar en el café los domingos` | Agent MCP-searches `#groups-directory`, replies in Spanish with **group match cards** — Café Volunteering on top, with schedule, contact james-t, and an **🤝 Introduce me** button |
| 4 | Lucía | Tap **🤝 Preséntame** on the Café Volunteering card | Ephemeral "Introducing you…" note, then a ✅ confirmation in Spanish |
| 5 | — | Switch view to `#cafe-volunteers` | A warm English intro posted by Threshold, tagging **@Lucía** and naming **james-t** |
| 6 | Operator | In any channel: `/threshold-impact` | Dashboard: 1 welcomed, ES served, 1 matched, 1 intro posted, **0 referrals needed**, avg. time to first connection ≈ the last minute |

That's the whole story: *she never needed to know the right person — the agent
was the referral.*

## Extended beats (after the opening, if time allows)

**Multilingual robustness (Arabic — non-Latin script).** As a second persona
(or after clearing Lucía's DM), join with a different account, pick **🇸🇦 العربية**,
and type: `أريد أن ألتقي بأشخاص جدد` ("I want to meet new people"). The agent
answers in Arabic with match cards (Arabic Community Group + New Members
Fellowship).

**Free-text language detection (no picker).** From a fresh account, ignore the
dropdown and just type `Dzień dobry, szukam grupy dla rodzin` — the agent
detects Polish, saves it, and answers in Polish with the Families group card.

**Digest (Flow C).** Operator runs `/threshold-digest`. Threshold reads
`#announcements` via MCP and DMs each opted-in member a 3–5 bullet digest in
*their* language — show Lucía's Spanish copy on screen.

**Close.** Re-run `/threshold-impact`: every number is real, logged by the
agent during the takes you just filmed.

## Talking points that map to what's on screen

- The group search and intro post go through the **Slack MCP Server**
  (`mcp.slack.com`) — the directory lives *in Slack*, not in the bot.
- Everything is Block Kit: welcome card, match cards, dashboard.
- Zero referrals needed — the metric the whole project exists to hold at zero.
- All names, groups, and messages are synthetic.

## After the final take

Leave the workspace **pristine for judging**:

```sh
python -m seed.reset_workspace
```

then re-run one quick Flow B pass (any persona) so `/threshold-impact` shows a
small, real, non-zero set of numbers for judges — and confirm the container is
still running (`docker ps`).
