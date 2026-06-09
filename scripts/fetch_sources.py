"""Daily ingestion orchestrator (stdlib only).

Pipeline: load config -> fetch each enabled source (fault-isolated) -> parse ->
filter to the recency window -> dedup vs seen-ids -> write state/raw-YYYY-MM-DD.json
-> persist updated seen-ids. Designed to be idempotent within a day (re-run yields
0 new items) and to never abort because one feed is down.

Run from repo root:  python scripts/fetch_sources.py
"""
import json
import os
import sys
from datetime import datetime, timezone

# Script dir is on sys.path[0] when run directly, so sibling imports resolve.
import http_fetch
import feed_parsers
from dedup_state import SeenStore

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(ROOT, "config")
STATE_DIR = os.path.join(ROOT, "state")


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _within_window(published_iso, now, window_hours):
    """True if item is recent enough. Undated items are kept (deduped later)."""
    if not published_iso:
        return True
    try:
        dt = datetime.fromisoformat(published_iso)
    except ValueError:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_hours = (now - dt).total_seconds() / 3600.0
    return -1 <= age_hours <= window_hours  # small negative tolerance for clock skew


def _parse_by_type(source, raw_bytes):
    stype = source.get("type", "rss")
    if stype == "hf_json":
        return feed_parsers.parse_hf_json(raw_bytes)
    return feed_parsers.parse_feed(raw_bytes)  # rss/atom auto-detect


def fetch_all():
    sources = _load_json(os.path.join(CONFIG_DIR, "sources.json"))
    ranking = _load_json(os.path.join(CONFIG_DIR, "ranking.json"))
    window_hours = ranking.get("window_hours", 36)
    now = datetime.now(timezone.utc)

    store = SeenStore().load()
    collected = {"academic": [], "news": []}
    seen_in_run = set()
    sources_ok, sources_failed = [], []

    for tier in ("academic", "news"):
        for source in sources.get(tier, []):
            if not source.get("enabled", True):
                continue
            sid = source["id"]
            try:
                raw_bytes = http_fetch.fetch(source["url"])
                items = _parse_by_type(source, raw_bytes)
            except Exception as err:  # noqa: BLE001 - per-source fault isolation
                sources_failed.append({"id": sid, "label": source.get("label", sid),
                                       "error": str(err)[:200]})
                continue

            kept = 0
            for it in items:
                item_id = it["id"]
                if not _within_window(it.get("published"), now, window_hours):
                    continue
                if store.is_seen(item_id) or item_id in seen_in_run:
                    continue
                seen_in_run.add(item_id)
                store.mark_seen(item_id)
                it.update({"source_id": sid, "source_label": source.get("label", sid),
                           "tier": tier})
                collected[tier].append(it)
                kept += 1
            sources_ok.append({"id": sid, "label": source.get("label", sid), "new_items": kept})

    return now, window_hours, store, collected, sources_ok, sources_failed


def write_raw(now, window_hours, collected, sources_ok, sources_failed):
    day = now.date().isoformat()
    for tier in collected:
        collected[tier].sort(key=lambda x: x.get("published") or "", reverse=True)
    payload = {
        "date": day,
        "generated_at": now.isoformat(),
        "window_hours": window_hours,
        "counts": {"academic": len(collected["academic"]), "news": len(collected["news"]),
                   "total": len(collected["academic"]) + len(collected["news"])},
        "sources_ok": sources_ok,
        "sources_failed": sources_failed,
        "items": collected,
    }
    os.makedirs(STATE_DIR, exist_ok=True)
    out_path = os.path.join(STATE_DIR, f"raw-{day}.json")
    # Same-day re-run guard: if today's raw already exists and this run found
    # nothing new (everything already deduped), preserve the original instead of
    # wiping it to empty. A genuine quiet first run still writes its empty file.
    if os.path.exists(out_path) and payload["counts"]["total"] == 0:
        return out_path, payload, False
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
    return out_path, payload, True


def main():
    now, window_hours, store, collected, ok, failed = fetch_all()
    out_path, payload, wrote = write_raw(now, window_hours, collected, ok, failed)
    store.save()
    c = payload["counts"]
    print(f"raw written: {out_path}" if wrote
          else f"raw preserved (same-day re-run, 0 new): {out_path}")
    print(f"new items: academic={c['academic']} news={c['news']} total={c['total']}")
    print(f"sources ok: {len(ok)} | failed: {len(failed)}")
    for f in failed:
        print(f"  FAILED {f['id']}: {f['error']}")
    print(f"seen-ids tracked: {len(store)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
