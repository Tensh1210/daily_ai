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

**Active setup: local Windows Task Scheduler + headless `claude` CLI**, daily at
**13:00 Asia/Saigon**. The CLI runs the full routine (fetch → curate with AI →
Discord → commit + push) using your Claude Pro plan quota.

> Why not the Anthropic cloud `/schedule` routine? Its sandbox filters network egress
> — only GitHub-style domains are reachable, so arXiv/HF/OpenAI/DeepMind fetches and
> the Discord webhook all return HTTP 403, and the sandbox lacks repo write access.
> This fetch-many-domains + webhook workload needs unrestricted egress, so it runs
> locally. (The disabled cloud routine config is kept for reference.)

### One-time setup

1. **Claude CLI logged in** (Pro plan): run `claude` once and `/login`.
2. **Discord webhook** as a persistent user env var (Command Prompt):
   ```cmd
   setx DISCORD_WEBHOOK_URL "https://discord.com/api/webhooks/xxx/yyy"
   ```
   (Open a NEW terminal afterwards so the variable is visible.)
3. **Create the scheduled task** (Command Prompt):
   ```cmd
   schtasks /Create /TN "DailyAIDigest" /TR "D:\Project\dailynews\routine\run-local-digest.cmd" /SC DAILY /ST 13:00 /F
   ```

The task runs `routine/run-local-digest.cmd`, which calls the Claude CLI headless and
appends output to `state/_run.log` (gitignored). The machine must be on at 13:00.

Manual run / test any time:
```cmd
routine\run-local-digest.cmd
```

## Delivery

**Primary channel: Discord webhook** (`scripts/send_discord.py`, stdlib). Simplest to
run unattended — one secret, no OAuth. The routine posts a compact message (the two
curated sections + a link to the full digest on GitHub); long bodies auto-split under
Discord's 2000-char limit.

Get a webhook: Discord → Server Settings → Integrations → Webhooks → New Webhook →
copy URL. Then set the env var:

| Var | Notes |
|-----|-------|
| `DISCORD_WEBHOOK_URL` | full `https://discord.com/api/webhooks/...` URL (secret) |
| `DISCORD_USERNAME` | optional display-name override |

Test locally (PowerShell):
```
$env:DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/…"
python scripts/send_discord.py --body "AI Daily Digest — test"
```

**For the cloud routine:** add `DISCORD_WEBHOOK_URL` as an environment secret in your
Claude Code environment settings (https://claude.ai/code) so the cloud sandbox can
read it. Without it the routine notes the skip and continues.

### Email (kept, currently disabled)

`scripts/send_email.py` (SMTP, stdlib `smtplib`) and the Gmail MCP `create_draft`
fallback remain in the repo but are **not called** by the routine right now. To
re-enable email, add a `send_email.py` step back into `routine/daily-digest-prompt.md`
and configure these env vars:

| Var | Default | Notes |
|-----|---------|-------|
| `DIGEST_SMTP_HOST` | `smtp.gmail.com` | |
| `DIGEST_SMTP_PORT` | `587` | STARTTLS |
| `DIGEST_SMTP_USER` | — | sender Gmail address |
| `DIGEST_SMTP_PASSWORD` | — | Gmail **App password** (requires 2-Step Verification) |
| `DIGEST_EMAIL_TO` | `phamthanhtin1210@gmail.com` | recipient |

## State & persistence

- `state/seen-ids.json` (tracked) prevents the same item appearing on consecutive days; entries expire after 7 days.
- `state/raw-*.json` is gitignored and regenerated each run.
- Persistence depends on the digest + seen-ids being committed each run — otherwise next-day dedup regresses.
