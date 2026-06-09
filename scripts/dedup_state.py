"""Seen-id persistence with 7-day TTL eviction (stdlib only).

State file maps a stable item id -> first-seen date (YYYY-MM-DD):
    { "arxiv:2506.12345": "2026-06-09", ... }
Items older than TTL_DAYS are evicted on load so the file does not grow forever.
"""
import json
import os
from datetime import date, datetime, timedelta

TTL_DAYS = 7
DEFAULT_STATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "state", "seen-ids.json"
)


class SeenStore:
    def __init__(self, path=DEFAULT_STATE_PATH):
        self.path = path
        self._seen = {}

    def load(self):
        """Load state and evict entries older than TTL_DAYS. Missing file = empty."""
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            raw = {}
        cutoff = date.today() - timedelta(days=TTL_DAYS)
        kept = {}
        for item_id, first_seen in raw.items():
            try:
                seen_date = datetime.strptime(first_seen, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue  # drop malformed entries
            if seen_date >= cutoff:
                kept[item_id] = first_seen
        self._seen = kept
        return self

    def is_seen(self, item_id):
        return item_id in self._seen

    def mark_seen(self, item_id, when=None):
        """Stamp an id with first-seen date (today by default). Idempotent."""
        if item_id not in self._seen:
            self._seen[item_id] = (when or date.today()).isoformat()

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._seen, fh, indent=2, sort_keys=True, ensure_ascii=False)

    def __len__(self):
        return len(self._seen)
