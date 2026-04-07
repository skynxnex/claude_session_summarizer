#!/usr/bin/env python3
"""
Claude Code Stop hook — session state summarizer.

Maintains SESSION.md in the project directory with compact working state:
current focus, recent decisions, open threads, key files.

Supports both Vertex AI (CLAUDE_CODE_USE_VERTEX=1) and direct Anthropic API.
Always exits 0 — never blocks Claude.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Config ───────────────────────────────────────────────────────────────────
MIN_MESSAGES_BETWEEN_UPDATES = 3
MAX_JSONL_CHARS = 40_000  # tail of transcript sent to model
MODEL_VERTEX = os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL", "claude-haiku-4-5@20251001")
MODEL_DIRECT = "claude-haiku-4-5-20251001"
VERTEX_PROJECT = os.environ.get("ANTHROPIC_VERTEX_PROJECT_ID", "")
VERTEX_REGION = os.environ.get("CLOUD_ML_REGION", "europe-west1")
USE_VERTEX = os.environ.get("CLAUDE_CODE_USE_VERTEX", "") == "1"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = (
    "You are a session-state summarizer for a software development AI assistant. "
    "Your output will be injected at the start of the NEXT session to restore working context. "
    "Be concise. Target ~400 words. Focus on STATE not DIALOGUE. Write in the same language as the conversation."
)

SESSION_TEMPLATE = """\
## Current Focus
{focus}

## Recent Decisions
{decisions}

## Open Threads
{open_threads}

## Key Files
{key_files}

## Context Notes
{context_notes}

---
_Last updated: {timestamp}_
"""


def main():
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        sys.exit(0)

    transcript_path = Path(payload.get("transcript_path", ""))
    cwd = Path(payload.get("cwd", ""))
    last_message = payload.get("last_assistant_message", "")

    if not cwd or not transcript_path:
        sys.exit(0)

    session_md = cwd / "SESSION.md"

    if not should_update(last_message, transcript_path, session_md):
        sys.exit(0)

    excerpt = read_tail(transcript_path, MAX_JSONL_CHARS)
    if not excerpt:
        sys.exit(0)

    existing = session_md.read_text(encoding="utf-8") if session_md.exists() else ""

    try:
        summary = call_model(excerpt, existing, str(cwd))
        session_md.write_text(summary, encoding="utf-8")
    except Exception:
        pass  # Always silent — never block Claude

    sys.exit(0)


def should_update(last_message: str, transcript_path: Path, session_md: Path) -> bool:
    if not session_md.exists():
        return True

    if len(last_message.strip()) < 150:
        return False

    # Count messages written after last SESSION.md update
    session_mtime = session_md.stat().st_mtime
    messages_since = 0
    if transcript_path.exists():
        for line in transcript_path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                entry = json.loads(line)
                # JSONL entries have a "timestamp" field (ISO8601)
                ts_str = entry.get("timestamp") or entry.get("ts")
                if ts_str:
                    from datetime import datetime
                    ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                    if ts > session_mtime:
                        messages_since += 1
            except Exception:
                pass

    if messages_since < MIN_MESSAGES_BETWEEN_UPDATES:
        return False

    # Check for signals of meaningful work in last message
    signals = [
        "implement", "creat", "fix", "refactor", "decision", "plan",
        "approach", "error", "fail", "success", "complet", "bygg",
        "skapar", "ändrar", "beslut", "klart", "färdig", "problem",
    ]
    return any(s in last_message.lower() for s in signals)


def read_tail(path: Path, max_chars: int) -> str:
    if not path.exists():
        return ""
    raw = path.read_text(encoding="utf-8", errors="replace")
    return raw[-max_chars:]


def call_model(transcript_excerpt: str, existing_session_md: str, cwd: str) -> str:
    prompt = f"""Project directory: {cwd}

Existing SESSION.md (may be empty on first run):
{existing_session_md or "(none)"}

Recent conversation transcript (JSONL, most recent messages):
{transcript_excerpt}

Write an updated SESSION.md using this exact structure:

## Current Focus
One sentence: what is actively being worked on right now.

## Recent Decisions
- Bullet list of architectural/design/approach decisions made this session. Skip trivial ones.

## Open Threads
- Bullet list of things mentioned but not yet done, open questions, or next steps.

## Key Files
- Bullet list of files created, modified, or central to current work (with path).

## Context Notes
Any domain knowledge, constraints, or non-obvious facts a new session needs to understand the situation.

---
_Last updated: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}_
"""

    messages = [{"role": "user", "content": prompt}]

    if USE_VERTEX and VERTEX_PROJECT:
        from anthropic import AnthropicVertex
        client = AnthropicVertex(project_id=VERTEX_PROJECT, region=VERTEX_REGION)
        response = client.messages.create(
            model=MODEL_VERTEX,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
    elif ANTHROPIC_API_KEY:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=MODEL_DIRECT,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
    else:
        return ""

    return response.content[0].text


if __name__ == "__main__":
    main()
