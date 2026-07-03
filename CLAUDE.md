# Auto Skill Finder — Claude Code Rules

## What This Skill Does

On every user prompt: automatically finds the best installed skill and activates caveman mode (~75% token reduction). No `/skill` command needed — fires on every message.

## Hook Integration

Two hooks in `hooks/`:
- `SessionStart.js` — writes caveman-active flag, emits caveman rules as system context
- `UserPromptSubmit.js` — scans skills, injects best match + caveman reinforcement

Install via: `node bin/install.js` or `bash install.sh`

## Skill Discovery Order

1. `~/.claude/skills/*/SKILL.md`
2. `~/.claude/plugins/*/skills/*/SKILL.md`
3. `~/skills/*/SKILL.md`

## Python Tooling

- `scripts/skill_finder.py` — core discovery engine, returns JSON
- `scripts/prompt_analyzer.py` — intent/entity extraction
- `scripts/build_index.py` — build searchable skill index cache

## Caveman Mode Rules

Every response: terse, fragments OK, drop filler/articles/pleasantries. Code exact. Technical terms exact. Off: "stop caveman" or "normal mode".

## Key Files

| File | Purpose |
|------|---------|
| `SKILL.md` | AI instruction set (single source of truth for routing logic) |
| `AGENTS.md` | Auto-discovery for OpenCode/Copilot/Cursor |
| `GEMINI.md` | Gemini CLI extension context |
| `hooks/UserPromptSubmit.js` | Per-prompt skill routing hook |
| `hooks/SessionStart.js` | Session setup hook |
| `scripts/skill_finder.py` | Core Python discovery engine |
| `config/agent-paths.json` | Agent-specific skill directory config |
| `bin/install.js` | Multi-agent installer |

## Rules for Agents Working Here

- Edit `SKILL.md` for routing logic changes
- Edit `hooks/*.js` for hook behavior
- Edit `scripts/skill_finder.py` for scoring algorithm
- Never hardcode paths — use `config/agent-paths.json`
- Caveman mode active here by default (this repo uses itself)
