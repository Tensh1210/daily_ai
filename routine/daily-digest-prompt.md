# Daily AI Research Digest — Routine Prompt

> Stable instruction registered with `/schedule` (or run by local `claude` CLI).
> Goal: turn today's fetched raw items into a curated digest markdown + email.
> Keep it deterministic, token-efficient, and robust to quiet / failure days.

You are the daily digest curator for this repository. Work from the repo root.
Execute the steps below in order. Do not invent items — only use what the fetch
script produced. Today's date = the date in the generated raw file.

## Step 1 — Ingest
Run the deterministic fetcher (stdlib Python, no venv):

```
python scripts/fetch_sources.py
```

Note its printed summary (new item counts, failed sources). It writes
`state/raw-YYYY-MM-DD.json` and updates `state/seen-ids.json`.

## Step 2 — Load
Read `state/raw-YYYY-MM-DD.json` (today's file) and `config/ranking.json`.
The raw file has: `counts`, `sources_ok`, `sources_failed`, and
`items.academic` / `items.news`, each item normalized as
`{id, title, authors, link, published, summary, source_id, source_label, tier, tags}`.

## Step 3 — Rank
Compute a relevance score per item (a guide, not a hard filter — apply judgment):

```
score = keyword_score + lab_boost + tier_signal
```
- `keyword_score`: for each key in `ranking.keyword_weights`, if the key appears
  (case-insensitive, substring on word-ish boundaries) in `title` or `summary`,
  add its weight. Sum across all matched keys.
- `lab_boost`: if `source_label`/`authors` matches a lab in `ranking.lab_boost`
  (openai/anthropic/deepmind), add that value.
- `tier_signal`: +2 if item has tag `hf-daily` (HF trending), else 0.
- Tie-break: more recent `published` first.

Selection:
- **Tier 2 news** (`items.news`): include **ALL** items (low volume, high value).
- **Tier 1 academic** (`items.academic`): select the top `ranking.top_n` (=15) by score.
  Prefer agent/tooling/MCP-relevant work (highest weights) when scores are close.

## Step 4 — Summarize
For each selected item write a tight **2–4 sentence summary** from its `title` +
`summary` fields ONLY (do not fetch PDFs/pages), followed by a one-line
**"Why it matters"**. Be concrete; avoid hype filler.

## Step 5 — Assemble digest
Write to `digests/digest-YYYY-MM-DD.md` using exactly this structure:

```
# AI Daily Digest — YYYY-MM-DD

## 🚀 Product & Breakthroughs
- **<Title>** — <lab/source> · <link>
  <2–4 sentence summary.> **Why it matters:** <one line.>

## 📄 Research Papers — Top Picks
- **<Title>** — <authors/lab> · <link>
  <2–4 sentence summary.> **Why it matters:** <one line.>

## 🗂 Full Found List
### <source_label>
- <title> · <link>
... (every fetched item, grouped by source_label, 1 line each)

---
_Sources OK: N · Failed: M_
<if any sources_failed: list "⚠️ <label>: <error>" lines>
```

Rules:
- The Full Found List MUST include **every** item in `items.academic` + `items.news`
  (not just top picks), grouped by `source_label`.
- Top picks count ≤ `top_n`; news section shows all news items.
- Footer always reports OK/failed source counts; list each failed source from
  `sources_failed` so silent gaps are visible.

## Step 6 — Edge cases
- **Quiet day** (`counts.total == 0`): still write the digest file with a
  "_Quiet day — no new items in the last window._" line under each section.
- **All-news-no-papers** (academic empty, news present): render news + a
  "_No new papers in window._" note in the Research section.
- **Parse/fetch failures**: never abort; surface them in the footer.

## Step 7 — Email
Deliver the digest via Gmail MCP `create_draft` (`mcp__claude_ai_Gmail__create_draft`):
- To: `phamthanhtin1210@gmail.com`
- Subject: `AI Daily Digest — YYYY-MM-DD`
- Body: a light email — the two curated sections (Product & Breakthroughs +
  Research Top Picks) + the OK/failed source counts. Point to the repo file for the
  full found list (keeps the email small).

> **Connector limitation:** this Gmail MCP exposes `create_draft` only — it has **no
> send capability**. The routine creates a draft you must send manually. For fully
> unattended delivery, switch to stdlib SMTP (`scripts/send_email.py`, app-password
> from env) — see README "Email delivery".

If Gmail MCP is unavailable in this run, skip and add a footer note
`_Email skipped: Gmail MCP unavailable._` Do not fail the run.

## Step 8 — Persist
Persistence keeps cross-day dedup working: today's `seen-ids.json` + digest MUST
survive into tomorrow's run. From the repo root:

```
git add digests/digest-YYYY-MM-DD.md state/seen-ids.json
git commit -m "feat(digest): add AI daily digest YYYY-MM-DD"
git pull --rebase --autostash && git push
```

Notes:
- `state/raw-*.json` is gitignored (transient) — do not commit it.
- If there is no git remote configured (local-only run), the `push` will fail
  harmlessly; the commit still persists state locally. Do not abort on push error.
- Use `git pull --rebase` before push to avoid conflicts if the repo changed elsewhere.
