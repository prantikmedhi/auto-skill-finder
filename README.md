# auto-skill-finder

**Universal AI skill router.** Send a prompt — the right skill loads automatically. No `/skill` commands. No manual selection. Works with Claude Code, Codex, Cursor, OpenCode, Gemini CLI, and any agent that reads `SKILL.md` or `AGENTS.md`.

Built-in caveman mode cuts response tokens by ~65–75% with zero accuracy loss.

---

## What it does

Every prompt you send:

1. **Scans** all installed skills across all your AI agents
2. **Scores** each skill against your prompt (name match, trigger keywords, description overlap)
3. **Loads** the best match silently — no announcement, no friction
4. **Compresses** skill content before injecting it (saves input tokens)
5. **Responds** in caveman mode (~75% fewer output tokens)

No configuration. No flags. Fires on every message.

---

## Token savings

| Source | Reduction |
|--------|-----------|
| Route to 1 skill vs loading all | ~95% of skill context skipped |
| Inline prose compression (no API) | ~10–50% off injected skill content |
| Caveman response mode | ~65–75% off AI responses |

---

## Install

### Claude Code (recommended)

```bash
git clone https://github.com/prantikmedhi/auto-skill-finder.git
cd auto-skill-finder
node bin/install.js
```

Hooks auto-wire into `~/.claude/settings.json`. Takes effect next session.

### All agents (auto-detect)

```bash
node bin/install.js          # installs for every detected agent
node bin/install.js --list   # see which agents were found
node bin/install.js --only cursor   # one agent only
```

Supports: Claude Code, Cursor, Gemini CLI, OpenCode, Codex, Cline.

### Manual (any agent)

Copy `SKILL.md` content into your agent's system prompt, rules file, or instructions. Copy `AGENTS.md` for agents that auto-discover it (OpenCode, Copilot).

---

## How skill routing works

Scoring (max 22 points per skill):

| Points | Condition |
|--------|-----------|
| +10 | Prompt names the skill explicitly |
| +5 each (max 15) | Trigger keyword match |
| +1 each (max 7) | Description word overlap |

Thresholds:
- **≥ 12** → auto-execute, no announcement
- **5–11** → load skill, one-line note
- **< 4** → fallback to general AI behavior

Skills are discovered from `~/.claude/skills/`, `~/.claude/plugins/`, `~/.cursor/skills/`, `~/.config/opencode/skills/`, `~/skills/`, and current directory.

---

## Build skill index (optional, faster routing)

Pre-index all your skills for instant lookup:

```bash
python3 scripts/build_index.py
# writes ~/.claude/auto-skill-index.json
```

Re-run after installing new skills.

---

## Compress files with caveman (full LLM compression)

For compressing large markdown files (CLAUDE.md, todo lists, memory files) using Claude API:

```bash
python3 scripts/cli.py path/to/file.md
```

- Compresses natural language prose into caveman format
- Preserves all code blocks, URLs, headings exactly
- Saves original backup to `~/.local/share/caveman-compress/backups/`
- Validates output before writing (auto-retries up to 2x)

Requires `ANTHROPIC_API_KEY` or `claude` CLI in PATH.

---

## Scripts reference

| Script | Purpose | API needed |
|--------|---------|------------|
| `scripts/skill_finder.py` | Core routing engine | No |
| `scripts/inline_compress.py` | Rule-based prose compression (runs in hook) | No |
| `scripts/prompt_analyzer.py` | Intent and entity extraction | No |
| `scripts/build_index.py` | Build searchable skill index cache | No |
| `scripts/detect.py` | Classify file as natural language vs code | No |
| `scripts/validate.py` | Verify compression preserved structure | No |
| `scripts/compress.py` | Full LLM-based caveman compression | Yes (Claude) |
| `scripts/cli.py` | CLI for compress.py | Yes (Claude) |

---

## Caveman mode

Always active. Drops articles, filler, pleasantries. Fragments OK. Technical terms exact. Code unchanged.

```
Not: "Sure! I'd be happy to help you with that..."
Yes: "Bug in auth middleware. Token expiry uses < not <=. Fix:"
```

Turns off: say `stop caveman` or `normal mode`.
Intensity levels: `lite`, `full` (default), `ultra`.

---

## Supported agents

| Agent | Mechanism | Auto-activates |
|-------|-----------|----------------|
| Claude Code | Hooks + skill | Yes |
| Cursor | `.cursor/rules/` MDC file | Yes |
| Gemini CLI | Extension via `gemini-extension.json` | Yes |
| OpenCode | `AGENTS.md` auto-discovery | Yes |
| Codex | `~/.codex/system-prompt.md` append | Yes |
| Cline | `.clinerules/` file | Yes |
| Copilot | `AGENTS.md` at repo root | Yes |
| Others | Paste `SKILL.md` into system prompt | Manual |

---

## File structure

```
auto-skill-finder/
├── SKILL.md              ← AI routing instructions (single source of truth)
├── AGENTS.md             ← OpenCode / Copilot / Cursor auto-discovery
├── GEMINI.md             ← Gemini CLI extension context
├── CLAUDE.md             ← Claude Code project rules
├── gemini-extension.json ← Gemini extension manifest
├── package.json
├── install.sh            ← Shell installer shim
├── bin/
│   └── install.js        ← Multi-agent installer
├── hooks/
│   ├── SessionStart.js       ← Caveman flag + system context
│   └── UserPromptSubmit.js   ← Per-prompt routing + compression
├── config/
│   └── agent-paths.json  ← Agent-specific skill dir config
└── scripts/
    ├── skill_finder.py       ← Core discovery engine
    ├── inline_compress.py    ← Rule-based compressor (no API)
    ├── prompt_analyzer.py    ← Intent extraction
    ├── build_index.py        ← Skill index cache
    ├── detect.py             ← File type detection
    ├── validate.py           ← Compression validator
    ├── compress.py           ← LLM-based caveman compressor
    └── cli.py                ← CLI entry point
```

---

## Requirements

- Node.js ≥ 18 (for installer and hooks)
- Python 3.10+ (for routing scripts)
- Claude Code, Cursor, Gemini CLI, OpenCode, or Codex installed

For LLM-based file compression: `ANTHROPIC_API_KEY` or `claude` CLI authenticated.

---

## Uninstall

```bash
node bin/install.js --uninstall
```

Removes hooks from `~/.claude/settings.json` and deletes hook files.

---

## License

MIT
