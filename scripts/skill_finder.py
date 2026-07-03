#!/usr/bin/env python3
"""
Auto Skill Finder — core discovery and scoring engine.
Scans installed skills across all supported AI agents and ranks against a prompt.
"""
from __future__ import annotations

import os
import re
import json
import argparse
from pathlib import Path
from typing import Optional

# ── Agent-specific skill directories ──────────────────────────────────────────

HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))

AGENT_SKILL_DIRS: list[Path] = [
    # Claude Code
    Path(os.environ.get("CLAUDE_CONFIG_DIR", HOME / ".claude")) / "skills",
    Path(os.environ.get("CLAUDE_CONFIG_DIR", HOME / ".claude")) / "plugins",
    # Cursor
    HOME / ".cursor" / "skills",
    # Gemini CLI
    HOME / ".gemini" / "skills",
    CONFIG / "gemini" / "skills",
    # OpenCode
    CONFIG / "opencode" / "skills",
    # Codex
    HOME / ".codex" / "skills",
    # Universal
    HOME / "skills",
    Path.cwd() / "skills",
]

STOPWORDS = {
    "a", "an", "the", "is", "to", "for", "with", "and", "or", "in", "of",
    "that", "it", "on", "at", "by", "from", "this", "be", "are", "was",
    "will", "can", "use", "when", "as", "if", "but", "not", "all", "any",
    "your", "you", "my", "me", "i", "we", "our", "its", "do", "does",
}

# ── Skill parsing ──────────────────────────────────────────────────────────────

def parse_skill(path: Path) -> Optional[dict]:
    """Parse a SKILL.md file. Returns dict or None on failure."""
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    fm_match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if not fm_match:
        return None

    fm = fm_match.group(1)

    name_m = re.search(r"^name:\s*(.+)", fm, re.MULTILINE)
    desc_m = re.search(r"^description:\s*>?\n?((?:[ \t]+.+\n?)+|.+)", fm, re.MULTILINE)
    triggers_m = re.search(r"^triggers:\s*\[(.+?)\]", fm, re.MULTILINE | re.DOTALL)

    name = name_m.group(1).strip() if name_m else path.parent.name
    description = ""
    if desc_m:
        raw = desc_m.group(1)
        description = re.sub(r"\s+", " ", raw).strip()
    triggers = []
    if triggers_m:
        triggers = [t.strip().strip("\"'") for t in triggers_m.group(1).split(",")]

    # First non-empty body paragraph as extra signal
    body = content[fm_match.end():]
    first_para = next((p.strip() for p in body.split("\n\n") if p.strip()), "")[:200]

    return {
        "name": name,
        "description": description,
        "triggers": triggers,
        "summary": first_para,
        "path": str(path),
    }

# ── Directory scanning ─────────────────────────────────────────────────────────

def scan_dirs(extra_dirs: list[str] | None = None) -> list[dict]:
    """Walk all agent skill dirs and return parsed skills (deduped by path)."""
    dirs = list(AGENT_SKILL_DIRS)
    if extra_dirs:
        dirs.extend(Path(d) for d in extra_dirs)

    skills: list[dict] = []
    seen: set[str] = set()

    for d in dirs:
        if not d.exists():
            continue
        try:
            for skill_md in d.rglob("SKILL.md"):
                key = str(skill_md.resolve())
                if key in seen:
                    continue
                seen.add(key)
                skill = parse_skill(skill_md)
                if skill:
                    skills.append(skill)
        except PermissionError:
            continue

    return skills

# ── Scoring ────────────────────────────────────────────────────────────────────

def _words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"\w+", text)} - STOPWORDS


# Context markers that introduce a trigger window
_TRIGGER_CTX_RE = re.compile(
    r"(?:use\s+(?:trigger|when|if)|trigger[s]?\s*:|"
    r"when\s+(?:the\s+)?user\s+(?:says?|mentions?|invokes?|asks?|types?)|"
    r"auto[- ]?trigger[s]?\s+when|invokes?\s+/)",
    re.IGNORECASE,
)

# Any quoted string (straight quotes only in source)
_QUOTED_RE = re.compile(r'"([^\n"\']{3,40})"')


def _extract_implicit_triggers(text: str) -> list[str]:
    """Extract trigger phrases from description patterns and quoted strings."""
    triggers: list[str] = []

    # For each trigger-context marker, capture text window and split on delimiters
    for m in _TRIGGER_CTX_RE.finditer(text):
        # Take up to 150 chars after the marker, first line only
        window = text[m.end(): m.end() + 150].split("\n")[0]
        parts = re.split(r",\s*|\bor\b|\band\b|/", window)
        for p in parts:
            # Strip leading stopwords, articles, punctuation
            t = p.strip().lstrip("\"' ").rstrip(".!? \"'")
            t = re.sub(r"^(when|with|if|the|a|an|user|says?|mentions?)\s+", "", t, flags=re.IGNORECASE)
            t = t.strip()
            if t and 3 <= len(t) < 60 and not t.startswith("http"):
                triggers.append(t.lower())

    # All quoted strings anywhere in description
    for m in _QUOTED_RE.finditer(text):
        t = m.group(1).strip().lower()
        if t and 3 <= len(t) < 40:
            triggers.append(t)

    return list(dict.fromkeys(triggers))  # dedupe, preserve order


def score_skill(skill: dict, prompt: str) -> tuple[int, str]:
    """Score skill vs prompt. Returns (score, reasoning_str)."""
    score = 0
    reasons: list[str] = []
    pl = prompt.lower()
    pw = _words(prompt)

    # Exact name match (+10)
    skill_name_variants = [
        skill["name"].lower(),
        skill["name"].lower().replace("-", " "),
        skill["name"].lower().replace("_", " "),
    ]
    if any(v in pl for v in skill_name_variants):
        score += 10
        reasons.append(f"name={skill['name']}")

    # Trigger keyword hits (+5 each, max 15)
    # Combine explicit triggers[] with implicit "Use when user says..." in description
    all_triggers = list(skill.get("triggers", []))
    all_triggers += _extract_implicit_triggers(skill.get("description", "") + " " + skill.get("summary", ""))

    trigger_hits = 0
    for t in all_triggers:
        tl = t.lower()
        t_words = {w for w in re.findall(r"\w+", tl) if w not in STOPWORDS and len(w) > 1}
        phrase_match = tl in pl
        full_word_match = bool(t_words) and t_words.issubset(pw)
        # Partial match: ≥60% of trigger words present (min 1 word)
        if t_words:
            matched_words = t_words & pw
            partial = len(matched_words) / len(t_words) >= 0.6
        else:
            partial = False

        if trigger_hits >= 3:
            break
        if phrase_match or full_word_match:
            score += 5
            trigger_hits += 1
            reasons.append(f"trigger={t}")
        elif partial and len(t_words) >= 2:
            score += 2
            trigger_hits += 1
            reasons.append(f"partial-trigger={t}")

    # Description word overlap (+1 each, max 7)
    dw = _words(skill["description"] + " " + skill.get("summary", ""))
    overlap = pw & dw
    overlap_score = min(len(overlap), 7)
    if overlap_score:
        score += overlap_score
        reasons.append(f"overlap={','.join(list(overlap)[:4])}")

    return score, "; ".join(reasons) if reasons else "no match"

# ── Main routing ───────────────────────────────────────────────────────────────

def route(
    prompt: str,
    extra_dirs: list[str] | None = None,
    threshold: int = 4,
) -> dict:
    """Route a prompt to the best skill. Returns routing decision dict."""
    skills = scan_dirs(extra_dirs)

    candidates: list[dict] = []
    for skill in skills:
        score, reason = score_skill(skill, prompt)
        candidates.append({
            "skill_name": skill["name"],
            "score": score,
            "reasoning": reason,
            "path": skill["path"],
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)

    # Dedupe by skill name — keep highest-scored path per name
    seen_names: set[str] = set()
    deduped: list[dict] = []
    for c in candidates:
        if c["skill_name"] not in seen_names:
            seen_names.add(c["skill_name"])
            deduped.append(c)
    candidates = deduped

    top3 = candidates[:3]

    selected: Optional[str] = None
    selected_path: Optional[str] = None
    if top3 and top3[0]["score"] >= threshold:
        selected = top3[0]["skill_name"]
        selected_path = top3[0]["path"]

    return {
        "analyzed_prompt": {"intent": prompt[:120], "implicit_needs": []},
        "candidate_skills": top3,
        "selected_skill": selected,
        "selected_skill_path": selected_path,
        "total_skills_scanned": len(skills),
    }

# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Auto Skill Finder")
    p.add_argument("--prompt", required=True, help="User prompt to route")
    p.add_argument("--skills-dir", nargs="+", dest="skills_dir", help="Extra skill dirs")
    p.add_argument("--threshold", type=int, default=4, help="Min score for match (default 4)")
    p.add_argument("--json", action="store_true", help="Output JSON")
    args = p.parse_args()

    result = route(args.prompt, args.skills_dir, args.threshold)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    sel = result["selected_skill"]
    print(f"Scanned: {result['total_skills_scanned']} skills")
    print(f"Selected: {sel or 'none (fallback)'}")
    if result["selected_skill_path"]:
        print(f"Path:     {result['selected_skill_path']}")
    print("\nTop candidates:")
    for c in result["candidate_skills"]:
        print(f"  [{c['score']:2d}] {c['skill_name']:30s}  {c['reasoning'][:60]}")


if __name__ == "__main__":
    main()
