"""Send the digest email via SMTP (stdlib only) for unattended delivery.

Credentials come from environment variables (never hardcode / commit):
    DIGEST_SMTP_HOST      default smtp.gmail.com
    DIGEST_SMTP_PORT      default 587 (STARTTLS)
    DIGEST_SMTP_USER      sender address (also default From)
    DIGEST_SMTP_PASSWORD  app-password (Gmail: account → App passwords, requires 2FA)
    DIGEST_EMAIL_TO       default recipient if --to omitted

Exit codes:
    0  sent
    2  not configured (missing user/password) — caller may fall back to a draft
    1  send failed (SMTP error)

Usage:
    python scripts/send_email.py --subject "AI Daily Digest — 2026-06-09" \
        --body-file digests/digest-2026-06-09.md [--to addr@example.com]
"""
import argparse
import os
import smtplib
import sys
from email.message import EmailMessage

DEFAULT_TO = "phamthanhtin1210@gmail.com"


def _config():
    return {
        "host": os.environ.get("DIGEST_SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("DIGEST_SMTP_PORT", "587")),
        "user": os.environ.get("DIGEST_SMTP_USER", ""),
        "password": os.environ.get("DIGEST_SMTP_PASSWORD", ""),
    }


def send(to_addr, subject, body, cfg=None):
    """Send a plain-text email. Returns an exit code (0 ok, 2 unconfigured, 1 fail)."""
    cfg = cfg or _config()
    if not cfg["user"] or not cfg["password"]:
        print("SMTP not configured (set DIGEST_SMTP_USER + DIGEST_SMTP_PASSWORD)",
              file=sys.stderr)
        return 2
    msg = EmailMessage()
    msg["From"] = cfg["user"]
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=30) as smtp:
            smtp.starttls()
            smtp.login(cfg["user"], cfg["password"])
            smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as err:
        print(f"SMTP send failed: {err}", file=sys.stderr)
        return 1
    print(f"sent to {to_addr} via {cfg['host']}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Send the digest email via SMTP.")
    ap.add_argument("--to", default=os.environ.get("DIGEST_EMAIL_TO", DEFAULT_TO))
    ap.add_argument("--subject", required=True)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--body-file", help="path to a file whose contents form the body")
    group.add_argument("--body", help="inline body text")
    args = ap.parse_args(argv)

    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as fh:
            body = fh.read()
    else:
        body = args.body
    return send(args.to, args.subject, body)


if __name__ == "__main__":
    sys.exit(main())
