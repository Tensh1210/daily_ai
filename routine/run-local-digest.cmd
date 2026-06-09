@echo off
REM Daily AI Research Digest - local runner (Plan B / option #1).
REM Invoked by Windows Task Scheduler. Runs the Claude Code CLI headless to
REM execute the full routine: fetch -> curate -> Discord -> commit + push.
REM
REM Prerequisites (one-time):
REM   1. Claude CLI logged in (Pro plan):        claude  (then /login once)
REM   2. Discord webhook as a persistent env var: setx DISCORD_WEBHOOK_URL "https://discord.com/api/webhooks/..."
REM
REM Output is appended to state\_run.log (gitignored).

cd /d "D:\Project\dailynews"

echo ============================================================>> state\_run.log
echo RUN %DATE% %TIME%>> state\_run.log

"C:\Users\PC\.local\bin\claude.exe" -p "Read routine/daily-digest-prompt.md and execute ALL of its steps for today. Be fully autonomous - do not ask questions: run scripts/fetch_sources.py, curate, write the full digest file, build the condensed Discord body and post it with scripts/send_discord.py, then commit and push digests/ and state/seen-ids.json. Report a short summary at the end." --dangerously-skip-permissions >> state\_run.log 2>&1

echo EXIT %ERRORLEVEL% at %DATE% %TIME%>> state\_run.log
