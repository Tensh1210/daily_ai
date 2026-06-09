# Daily AI Research Digest

A daily routine that aggregates the latest **AI research papers** + **product/breakthrough news**
from free RSS/JSON sources (no paid APIs), curates the most relevant items, and produces:

- a committed markdown digest at `digests/digest-YYYY-MM-DD.md`, and
- an email to the configured recipient (via Gmail MCP).

**Design principle:** separate *deterministic ingestion* (a stdlib Python script) from
*smart curation* (Claude reads the raw items and writes the digest). Full design doc:
`docs/daily-ai-research-digest-design.md`.

## How it works

```
1. python scripts/fetch_sources.py
   → fetch RSS/Atom + HF daily_papers JSON, filter to a recency window,
     dedup against seen-ids (7-day TTL)
   → write state/raw-YYYY-MM-DD.json  (the full found list)
   → update state/seen-ids.json
2. Claude (routine agent) reads the raw JSON + config/ranking.json
   → ranks, selects top-N research picks + all news, writes deep summaries
   → writes digests/digest-YYYY-MM-DD.md  (2 curated sections + full found list)
3. git commit digest + seen-ids   (persist dedup state across runs)
4. email the digest via Gmail MCP  (graceful skip if unavailable)
```

Steps 2–4 are driven by `routine/daily-digest-prompt.md` — the stable instruction the scheduler runs.

## Layout

```
config/   sources.json (2 feed tiers) · ranking.json (keyword weights, top_n, window)
scripts/  http_fetch.py · feed_parsers.py · dedup_state.py · fetch_sources.py
state/    seen-ids.json (tracked) · raw-YYYY-MM-DD.json (gitignored, transient)
digests/  digest-YYYY-MM-DD.md (tracked history)
routine/  daily-digest-prompt.md (the scheduled prompt)
```

## Run the fetcher locally

Requires only Python 3.9+ (standard library — no venv, no pip install):

```
python scripts/fetch_sources.py
```

Prints new-item counts + any failed sources, and writes today's `state/raw-*.json`.
Re-running the same day is safe: it finds 0 new items and preserves the existing raw file.

## Configuration

**`config/sources.json`** — two tiers of feeds. Each source has `id`, `type`
(`rss` | `hf_json`), `url`, `label`, and `enabled` (set `false` to disable without deleting).
RSS and Atom are auto-detected. Microsoft Research is omitted (its feed returns HTTP 403).

**`config/ranking.json`**
- `top_n` — number of research papers to feature (default 15). News items are all included.
- `window_hours` — recency window for fetched items (default 36).
- `keyword_weights` — relevance scoring. HIGH = agents/tooling/MCP (weight 4),
  MED = LLM-core + multimodal/efficiency (weight 2).
- `lab_boost` — extra score for items from openai/anthropic/deepmind.

## Scheduling

The same scripts/config/prompt are reused regardless of trigger.

### Option A — Cloud `/schedule` (preferred)

Runs in Anthropic's cloud at the cron time even when your machine is off.
**Requires the repo on GitHub** so the routine can commit + push state back (persistence).

1. Put this repo on GitHub: `git init`, commit, create a GitHub remote, push.
2. Register a scheduled routine pointing at `routine/daily-digest-prompt.md`,
   cron **07:00 Asia/Saigon** daily.
3. The routine ends by committing `digests/` + `state/seen-ids.json` and pushing.

> Capability caveat (Risk #1/#2): the cloud sandbox must support `git push` back to the
> repo and the Gmail MCP connector. If either is unavailable, use Option B.

### Option B — Local (Plan B, fallback)

Windows Task Scheduler triggers the headless `claude` CLI on this machine.

1. Create a daily task at **07:00** (Asia/Saigon) running, from the repo root:
   `claude -p "$(type routine\daily-digest-prompt.md)"` (or point the CLI at the prompt file).
2. Commit-back is local (no remote needed); state stays on disk.
3. Con: the machine must be powered on at the scheduled time.

## Email delivery

The routine sends the digest via **SMTP** (`scripts/send_email.py`, stdlib `smtplib`)
for fully unattended delivery, and falls back to a **Gmail MCP draft** if SMTP is not
configured (the Gmail connector can draft but not send).

Configure SMTP via environment variables (never committed):

| Var | Default | Notes |
|-----|---------|-------|
| `DIGEST_SMTP_HOST` | `smtp.gmail.com` | |
| `DIGEST_SMTP_PORT` | `587` | STARTTLS |
| `DIGEST_SMTP_USER` | — | sender Gmail address |
| `DIGEST_SMTP_PASSWORD` | — | Gmail **App password** (Google account → Security → App passwords; requires 2-Step Verification) |
| `DIGEST_EMAIL_TO` | `phamthanhtin1210@gmail.com` | recipient |

Test locally:
```
set DIGEST_SMTP_USER=you@gmail.com        # PowerShell: $env:DIGEST_SMTP_USER="you@gmail.com"
set DIGEST_SMTP_PASSWORD=your-app-password
python scripts/send_email.py --subject "AI Daily Digest — test" --body "hello"
```

**For the cloud routine:** add `DIGEST_SMTP_USER` + `DIGEST_SMTP_PASSWORD` as
environment secrets in your Claude Code environment settings
(https://claude.ai/code) so the cloud sandbox can read them. Without them the routine
falls back to creating a Gmail draft.

## State & persistence

- `state/seen-ids.json` (tracked) prevents the same item appearing on consecutive days; entries expire after 7 days.
- `state/raw-*.json` is gitignored and regenerated each run.
- Persistence depends on the digest + seen-ids being committed each run — otherwise next-day dedup regresses.
