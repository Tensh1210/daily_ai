"""Minimal stdlib HTTP fetcher: User-Agent, timeout, light retry/backoff.

arXiv and some CDNs reject requests without a User-Agent, so one is always set.
Redirects (e.g. OpenAI 307) are followed by urllib's default redirect handler.
"""
import time
import urllib.error
import urllib.request

# Descriptive UA — arXiv blocks the default python-urllib agent.
USER_AGENT = "Mozilla/5.0 (compatible; DailyAIDigest/1.0; +https://github.com/)"
DEFAULT_TIMEOUT = 30
MAX_RETRIES = 2
BACKOFF_BASE = 2  # seconds; sleep = BACKOFF_BASE * attempt


class FetchError(Exception):
    """Raised when a URL cannot be fetched after retries. Caller decides to skip."""


def fetch(url, timeout=DEFAULT_TIMEOUT):
    """Fetch a URL and return raw bytes. Retries transient failures with backoff.

    Raises FetchError on permanent failure so the orchestrator can skip the source
    without aborting the whole run.
    """
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as err:
            last_err = err
            # HTTP 4xx (except 429) are not worth retrying — fail fast.
            status = getattr(err, "code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                break
            if attempt < MAX_RETRIES:
                time.sleep(BACKOFF_BASE * (attempt + 1))
    raise FetchError(f"failed to fetch {url}: {last_err}")
