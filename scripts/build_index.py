#!/usr/bin/env python3
"""
Build Index — scans all agent skill dirs and writes a JSON cache at ~/.claude/auto-skill-index.json.
Run this after installing new skills to update the search index.
"""
from __future__ import annotations

import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Import from same package
import sys
sys.path.insert(0, str(Path(__file__).parent))
from skill_finder import scan_dirs, AGENT_SKILL_DIRS

DEFAULT_INDEX = Path.home() / ".claude" / "auto-skill-index.json"


def file_hash(path: Path) -> str:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()[:8]
    except OSError:
        return "?"


def build_index(output: Path, extra_dirs: list[str] | None = None) -> dict:
    skills = scan_dirs(extra_dirs)

    index = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "total": len(skills),
        "skills": [],
    }

    for s in skills:
        p = Path(s["path"])
        index["skills"].append({
            "name": s["name"],
            "description": s["description"],
            "triggers": s["triggers"],
            "path": s["path"],
            "hash": file_hash(p),
        })

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def main() -> None:
    p = argparse.ArgumentParser(description="Build skill search index")
    p.add_argument("--output", default=str(DEFAULT_INDEX), help="Output JSON path")
    p.add_argument("--skills-dir", nargs="+", dest="skills_dir")
    p.add_argument("--list-dirs", action="store_true", help="Print scanned dirs and exit")
    args = p.parse_args()

    if args.list_dirs:
        for d in AGENT_SKILL_DIRS:
            exists = "✓" if d.exists() else "✗"
            print(f"  {exists} {d}")
        return

    out = Path(args.output)
    index = build_index(out, args.skills_dir)
    print(f"Index built: {out}")
    print(f"Skills found: {index['total']}")
    for s in index["skills"]:
        print(f"  {s['name']:30s}  {s['description'][:60]}")


if __name__ == "__main__":
    main()
