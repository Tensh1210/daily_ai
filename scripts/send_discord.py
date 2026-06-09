"""Post the digest to a Discord channel via webhook (stdlib only).

Discord webhooks need no bot/OAuth — just a webhook URL (Server Settings →
Integrations → Webhooks). The URL is a secret, read from the environment:
    DISCORD_WEBHOOK_URL   the full https://discord.com/api/webhooks/... URL
    DISCORD_USERNAME      optional display name override for the post

Discord caps a message at 2000 chars, so long bodies are split into multiple
posts on line boundaries. Exit codes mirror send_email.py:
    0  posted
    2  not configured (no webhook URL) — caller may fall back to another channel
    1  post failed

Usage:
    python scripts/send_discord.py --body-file digests/digest-2026-06-09.md
    python scripts/send_discord.py --body "quick note"
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

MAX_LEN = 1900  # leave margin under Discord's 2000-char hard limit


def _chunk(text, limit=MAX_LEN):
    """Split text into <=limit pieces, preferring line boundaries."""
    chunks, buf = [], ""
    for line in text.splitlines(keepends=True):
        # A single over-long line is hard-split.
        while len(line) > limit:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(line[:limit])
            line = line[limit:]
        if len(buf) + len(line) > limit:
            chunks.append(buf)
            buf = line
        else:
            buf += line
    if buf.strip():
        chunks.append(buf)
    return chunks or [""]


def post(body, webhook=None, username=None):
    webhook = webhook or os.environ.get("DISCORD_WEBHOOK_URL", "")
    username = username or os.environ.get("DISCORD_USERNAME", "")
    if not webhook:
        print("Discord not configured (set DISCORD_WEBHOOK_URL)", file=sys.stderr)
        return 2
    chunks = _chunk(body)
    for i, chunk in enumerate(chunks):
        payload = {"content": chunk}
        if username:
            payload["username"] = username
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "DailyAIDigest/1.0"},
        )
        try:
            urllib.request.urlopen(req, timeout=30).read()
        except urllib.error.HTTPError as err:
            # 429 = rate limited; honor retry-after once.
            if err.code == 429:
                retry = float(err.headers.get("Retry-After", "1"))
                time.sleep(min(retry, 10) + 0.5)
                try:
                    urllib.request.urlopen(req, timeout=30).read()
                except (urllib.error.URLError, OSError) as e2:
                    print(f"Discord post failed (after retry): {e2}", file=sys.stderr)
                    return 1
            else:
                print(f"Discord post failed: HTTP {err.code} {err.reason}", file=sys.stderr)
                return 1
        except (urllib.error.URLError, OSError) as err:
            print(f"Discord post failed: {err}", file=sys.stderr)
            return 1
        if i < len(chunks) - 1:
            time.sleep(0.6)  # gentle pacing between multi-part posts
    print(f"posted {len(chunks)} message(s) to Discord")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Post the digest to Discord via webhook.")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--body-file", help="path to a file whose contents form the post")
    group.add_argument("--body", help="inline post text")
    args = ap.parse_args(argv)

    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as fh:
            body = fh.read()
    else:
        body = args.body
    return post(body)


if __name__ == "__main__":
    sys.exit(main())
