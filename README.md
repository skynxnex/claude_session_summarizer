# claude_session_summarizer

Claude Code Stop hook that maintains `SESSION.md` in your project directory after each session. The file is automatically loaded at the start of the next session to restore working context.

## What it does

When Claude Code ends a session, this hook reads the conversation transcript and calls Claude Haiku to write a compact `SESSION.md` with:

- **Current Focus** — what was actively being worked on
- **Recent Decisions** — architectural and design choices made
- **Open Threads** — unfinished work, open questions, next steps
- **Key Files** — files created or central to current work
- **Context Notes** — domain knowledge a new session needs

Updates are skipped for trivial sessions (short last message, fewer than 3 new messages, no signals of meaningful work).

## Setup

Register as a Claude Code Stop hook in `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/session_summarizer/session_summarizer.py"
          }
        ]
      }
    ]
  }
}
```

## Authentication

Supports two modes — the script auto-detects which to use:

**Vertex AI** (set `CLAUDE_CODE_USE_VERTEX=1`):
```
CLAUDE_CODE_USE_VERTEX=1
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project
CLOUD_ML_REGION=europe-west1          # default
ANTHROPIC_DEFAULT_HAIKU_MODEL=...     # optional override
```

**Direct Anthropic API** (fallback):
```
ANTHROPIC_API_KEY=sk-ant-...
```

If neither is configured the hook exits silently without writing anything.

## Requirements

```
anthropic
```

Install: `pip install anthropic`

## Behaviour notes

- Always exits `0` — never blocks Claude from finishing
- Silent on all errors — never surfaces exceptions to the user
- Writes in the same language as the conversation
- `SESSION.md` is a project-local file; add it to `.gitignore` if you don't want it committed
