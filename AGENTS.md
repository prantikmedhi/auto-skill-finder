@./SKILL.md

# Auto Skill Finder — Agent Rules

This file is auto-loaded by: OpenCode, GitHub Copilot (AGENTS.md), Cursor (via --with-init), Cline, Junie, Trae, and any agent that discovers root AGENTS.md.

## Always-On Behavior

Every prompt you receive: run the auto-skill-finder routing logic below, then respond in caveman mode.

## Routing Logic

1. Scan `~/skills/*/SKILL.md`, `~/.claude/skills/*/SKILL.md`, `~/.config/opencode/skills/*/SKILL.md`, `.cursor/rules/*.md` for installed skills.
2. For each skill, score against current prompt:
   - +10 if prompt names the skill explicitly
   - +5 per trigger keyword hit (max 15)
   - +1 per description word overlap (max 7)
3. Score ≥ 12 → silently load and execute that skill
4. Score 5–11 → load skill, one-line note "Using [name]."
5. Score < 5 → answer normally

## Caveman Mode (Permanent)

Respond terse like smart caveman. Drop articles/filler/pleasantries/hedging. Fragments OK. Technical terms exact. Code unchanged. Off only: "stop caveman" / "normal mode".

## Python Acceleration

If Python available: `python scripts/skill_finder.py --prompt "<user-prompt>" --json`
Returns JSON with `selected_skill`, `selected_skill_path`, `candidate_skills`.
Load `selected_skill_path` if score ≥ 5.
