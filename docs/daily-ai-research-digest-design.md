# Daily AI Research Digest — Design Doc

> Status: APPROVED (brainstorm) · Date: 2026-06-09 · Owner: PC
> Next: `/ck:plan` → phase breakdown

## 1. Problem Statement

Build a Claude Code routine that runs daily, aggregates latest AI research + product/breakthrough
news from free RSS/JSON sources (no paid APIs), curates top picks, and outputs a digest
to a repo markdown file + email.

## 2. Requirements

### Functional
- Daily scheduled run via `/schedule` (cloud routine, cron).
- Fetch from 2 source tiers (academic papers + product/breakthrough news).
- Dedup across days (seen-ids, 7-day TTL).
- Rank → select top-N picks, deep summaries + "why it matters".
- Output: `digests/digest-YYYY-MM-DD.md` (committed to repo) + email via Gmail MCP.
- Full found list at end of digest (every item fetched, 1 line each).

### Non-functional
- Ingestion deterministic + cheap: Python **stdlib only** (no venv — cloud sandbox has none).
- Per-source fault isolation: one dead feed ≠ whole job fails.
- KISS/YAGNI/DRY. Each code file < 200 LoC.

### Scope boundary (OUT)
- No paid APIs, no LLM-based fetching of raw feeds (script does ingestion).
- No web UI/dashboard (markdown + email only).
- No multi-user / no auth system.

### Non-negotiable constraints
- Free sources only (RSS/Atom/public JSON).
- Stdlib-only fetch script.
- Output paths: `digests/`, state in `state/`, config in `config/`.

## 3. Architecture

### Principle
Separate **deterministic ingestion (script)** from **smart curation (Claude)**.

### Daily flow
```
1. python scripts/fetch_sources.py
   → parse RSS/Atom + HF daily_papers JSON, filter ~24-36h window, dedup vs seen-ids
   → write state/raw-YYYY-MM-DD.json (full found list)
   → update state/seen-ids.json (id → first_seen; evict > 7 days)
2. Claude (routine agent) reads raw JSON
   → rank by config/ranking.json keyword weights + heuristics
   → select top-N, write deep summaries + "why it matters"
   → write digests/digest-YYYY-MM-DD.md (2 sections + full list)
3. git commit digest + seen-ids (persist state across runs)
4. send digest email via Gmail MCP (graceful if unavailable)
```

### File layout
```
dailynews/
├── README.md
├── config/
│   ├── sources.json        # 2 tiers: academic + news (TBD final list)
│   └── ranking.json        # keyword weights, top-N (TBD values)
├── scripts/
│   ├── fetch_sources.py    # orchestrator: load config → fetch → dedup → write raw
│   ├── feed_parsers.py     # arxiv/atom/rss parser + HF daily_papers JSON parser
│   ├── http_fetch.py       # urllib wrapper: User-Agent, timeout, light retry
│   └── dedup_state.py      # seen-ids load/save + TTL eviction
├── state/
│   ├── seen-ids.json
│   └── raw-YYYY-MM-DD.json
├── digests/
│   └── digest-YYYY-MM-DD.md
└── routine/
    └── daily-digest-prompt.md   # stable prompt registered with /schedule
```

## 4. Sources

### Tier 1 — Academic Papers
| Source | Mechanism | Status |
|---|---|---|
| arXiv cs.CL / cs.AI / cs.IR | RSS `https://rss.arxiv.org/rss/cs.CL` (+cs.AI, cs.IR) | ✅ free, abstract inline |
| Hugging Face Papers | JSON `https://huggingface.co/api/daily_papers` (no key) | ✅ endpoint, no HTML scrape |
| Papers With Code | — | ❌ sunset 2025, dropped |

### Tier 2 — Product & Breakthrough News (verified live 2026-06-09)
| Source | Feed | Status |
|---|---|---|
| OpenAI News | `https://openai.com/news/rss.xml` | ✅ official RSS 2.0 |
| OpenAI Research | `https://openai.com/blog/rss.xml` | ✅ official |
| Anthropic News | `https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml` | ✅ community (no native RSS) |
| Anthropic Engineering | `.../feed_anthropic_engineering.xml` | ✅ — MCP/Skills/Agent announcements land here |
| Anthropic Research | `.../feed_anthropic_research.xml` | ✅ community |
| Google DeepMind | `https://deepmind.google/blog/rss.xml` | ✅ official |
| Meta AI | `.../feed_meta_ai.xml` (Olshansk) | ✅ community |
| Microsoft Research | TBD verify at plan time | ⚠️ |

**Editorial (optional, off by default):** MarkTechPost, MIT Tech Review AI, The Batch (DeepLearning.AI).

## 5. Digest Format
```
# AI Daily Digest — YYYY-MM-DD

## 🚀 Product & Breakthroughs        (Tier 2, prioritized, model releases/tooling)
- **Title** — lab · link
  2-4 sentence summary + why it matters.

## 📄 Research Papers — Top Picks      (Tier 1, ~15 picks, keyword-ranked)
- **Title** — authors/lab · arXiv/HF link
  2-4 sentence summary + why it matters.

## 🗂 Full Found List                  (everything fetched, grouped by source, 1 line each)
### arXiv cs.CL
- title · link
...
```

## 6. Risks & Mitigations
| # | Risk | Severity | Mitigation |
|---|---|---|---|
| 1 | Persistence depends on git commit from cloud routine (seen-ids/digest must push back) | 🔴 High | **Validate `/schedule` commit+push first.** If unsupported → local fallback (Plan B). |
| 2 | Gmail MCP may be unavailable in cloud sandbox | 🟡 Med | Markdown is primary output; email graceful-fail. Alt: stdlib SMTP + app-password secret. |
| 3 | Olshansk community feeds (Anthropic/Meta) could stall | 🟡 Med | Monitor freshness; fallback scrape `anthropic.com/news` HTML. |
| 4 | HF JSON / blog feed shape changes | 🟡 Med | Per-source try/except; validate fields; skip on parse error. |
| 5 | arXiv UA / rate-limit | 🟢 Low | Set User-Agent, timeout, light retry/backoff. |

## 7. Plan B — Local Execution (fallback if Risk #1/#2 block cloud)
Run via Windows Task Scheduler + `claude` CLI headless on local machine.
Pros: venv, git creds, Gmail all local & stable. Con: machine must be on at cron time.
Same scripts/config reused — only the trigger mechanism differs.

## 8. Success Metrics
- Routine completes daily without manual intervention.
- Digest contains ≥1 Tier-2 item when a lab posts; top picks relevant to configured keywords.
- No duplicate items across consecutive days.
- One dead feed does not abort the run.

## 9. Decisions Locked
- Execution: script fetch (stdlib) + Claude curate.
- Output: repo markdown + Gmail email.
- Curation: top-N curated + full found list at bottom.
- Dedup: seen-ids.json, 7-day TTL.
- Sources: 2 tiers as above; PWC dropped.
- Scripts modularized into 4 files.

## 10. Open Questions (decide at plan/impl time)
1. Cron time + timezone (Asia/Saigon) — TBD.
2. `ranking.json` keyword weights — TBD by user.
3. N for top picks (default proposal: 15) — TBD.
4. Microsoft Research RSS URL — verify.
5. Email delivery mechanism final choice: Gmail MCP vs stdlib SMTP — pending Risk #2 validation.
6. Does `/schedule` cloud routine support git push + MCP? — must validate before build (Risk #1/#2).
