"""Feed parsers (stdlib only): RSS 2.0, Atom, and HF daily_papers JSON.

Each parser maps source-specific shapes to a common normalized item dict:
    {id, title, authors, link, published (ISO8601 UTC), summary, tags}
source_id / source_label / tier are attached later by the orchestrator.

Defensive by design: a malformed individual entry is skipped, not fatal.
"""
import json
import hashlib
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
import xml.etree.ElementTree as ET

ATOM_NS = "{http://www.w3.org/2005/Atom}"
DC_NS = "{http://purl.org/dc/elements/1.1/}"


class _TextStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks = []

    def handle_data(self, data):
        self._chunks.append(data)

    def text(self):
        return "".join(self._chunks)


def strip_html(raw):
    """Remove HTML tags/entities from a summary, collapse whitespace."""
    if not raw:
        return ""
    parser = _TextStripper()
    try:
        parser.feed(raw)
        out = parser.text()
    except Exception:
        out = raw
    return " ".join(out.split())


def to_iso_utc(value):
    """Parse RFC822 (RSS) or ISO8601 (Atom/JSON) dates → ISO8601 UTC string.

    Returns None when the date is missing/unparseable so the caller can decide.
    """
    if not value:
        return None
    dt = None
    try:
        dt = parsedate_to_datetime(value)  # RFC822, e.g. "Mon, 09 Jun 2026 12:00:00 +0000"
    except (TypeError, ValueError, IndexError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _hash_id(link):
    return "h:" + hashlib.sha1((link or "").encode("utf-8")).hexdigest()[:16]


def _arxiv_id(link, guid):
    """Stable arXiv id from abs link or guid; falls back to link hash."""
    for cand in (link or "", guid or ""):
        if "arxiv.org/abs/" in cand:
            return "arxiv:" + cand.split("arxiv.org/abs/")[-1].strip("/")
        if cand.startswith("oai:arXiv.org:"):
            return "arxiv:" + cand.split("oai:arXiv.org:")[-1]
    return _hash_id(link)


def _findtext(elem, *paths):
    for p in paths:
        node = elem.find(p)
        if node is not None and (node.text or "").strip():
            return node.text.strip()
    return ""


def parse_rss(xml_bytes):
    """RSS 2.0 <channel><item>. Handles arXiv dc:creator + arxiv ids."""
    root = ET.fromstring(xml_bytes)
    items = []
    for it in root.iter("item"):
        try:
            link = _findtext(it, "link")
            guid = _findtext(it, "guid")
            title = _findtext(it, "title")
            if not title:
                continue
            authors = _findtext(it, f"{DC_NS}creator", "author")
            summary = strip_html(_findtext(it, "description", f"{DC_NS}description"))
            published = to_iso_utc(_findtext(it, "pubDate", f"{DC_NS}date"))
            is_arxiv = "arxiv.org" in link or guid.startswith("oai:arXiv")
            item_id = _arxiv_id(link, guid) if is_arxiv else _hash_id(link or title)
            items.append({
                "id": item_id, "title": title, "authors": authors, "link": link,
                "published": published, "summary": summary, "tags": [],
            })
        except Exception:
            continue
    return items


def parse_atom(xml_bytes):
    """Atom <feed><entry>."""
    root = ET.fromstring(xml_bytes)
    items = []
    for e in root.iter(f"{ATOM_NS}entry"):
        try:
            title = _findtext(e, f"{ATOM_NS}title")
            if not title:
                continue
            link = ""
            for ln in e.findall(f"{ATOM_NS}link"):
                rel = ln.get("rel", "alternate")
                if rel == "alternate" or not link:
                    link = ln.get("href", link)
            entry_id = _findtext(e, f"{ATOM_NS}id") or link
            author = _findtext(e, f"{ATOM_NS}author/{ATOM_NS}name")
            summary = strip_html(_findtext(e, f"{ATOM_NS}summary", f"{ATOM_NS}content"))
            published = to_iso_utc(_findtext(e, f"{ATOM_NS}published", f"{ATOM_NS}updated"))
            items.append({
                "id": _hash_id(entry_id), "title": title, "authors": author, "link": link,
                "published": published, "summary": summary, "tags": [],
            })
        except Exception:
            continue
    return items


def parse_feed(xml_bytes):
    """Auto-detect RSS vs Atom by root tag."""
    root = ET.fromstring(xml_bytes)
    if root.tag.endswith("feed"):
        return parse_atom(xml_bytes)
    return parse_rss(xml_bytes)


def parse_hf_json(json_bytes):
    """Hugging Face /api/daily_papers → normalized items. Defensive field access."""
    data = json.loads(json_bytes)
    items = []
    for row in data if isinstance(data, list) else []:
        try:
            paper = row.get("paper", row) if isinstance(row, dict) else {}
            pid = paper.get("id") or row.get("id")
            title = (paper.get("title") or row.get("title") or "").strip()
            if not pid or not title:
                continue
            authors = ", ".join(
                a.get("name", "") for a in paper.get("authors", []) if isinstance(a, dict)
            ).strip(", ")
            summary = strip_html(paper.get("summary") or paper.get("abstract") or "")
            published = to_iso_utc(
                paper.get("publishedAt") or row.get("publishedAt") or paper.get("date")
            )
            items.append({
                "id": "hf:" + str(pid),
                "title": title,
                "authors": authors,
                "link": f"https://huggingface.co/papers/{pid}",
                "published": published,
                "summary": summary,
                "tags": ["hf-daily"],
            })
        except Exception:
            continue
    return items
