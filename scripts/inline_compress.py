#!/usr/bin/env python3
"""
Inline Compress — rule-based caveman prose compression.
No LLM call. Runs in hooks to shrink skill content before context injection.
Goal: ~40-60% token reduction on prose. Code blocks, URLs, headings untouched.

Usage:
    python inline_compress.py <filepath>           # compress file in-place
    python inline_compress.py --text "some prose"  # compress stdin string
    python inline_compress.py --skill <SKILL.md>   # compress + print (no write)
"""
from __future__ import annotations

import re
import sys
import argparse
from pathlib import Path

# ── Protected zone extraction ─────────────────────────────────────────────────
# Content inside these zones must NEVER be touched.

_FENCE_RE = re.compile(r"(`{3,}|~{3,})[^\n]*\n[\s\S]*?\1", re.MULTILINE)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_URL_RE = re.compile(r"https?://\S+")
_HEADING_RE = re.compile(r"^#{1,6}\s+.+", re.MULTILINE)

PLACEHOLDER = "\x00PROTECT{}\x00"


def _extract_protected(text: str) -> tuple[str, list[str]]:
    """Replace protected regions with numbered placeholders. Returns (text, protected_list)."""
    protected: list[str] = []

    def _replace(m: re.Match) -> str:
        idx = len(protected)
        protected.append(m.group(0))
        return PLACEHOLDER.format(idx)

    # Order matters: fences first (they can contain inline code)
    text = _FENCE_RE.sub(_replace, text)
    text = _INLINE_CODE_RE.sub(_replace, text)
    text = _URL_RE.sub(_replace, text)
    return text, protected


def _restore_protected(text: str, protected: list[str]) -> str:
    for i, original in enumerate(protected):
        text = text.replace(PLACEHOLDER.format(i), original)
    return text


# ── Compression rules ─────────────────────────────────────────────────────────

# Articles before words (drop "a", "an", "the" — but not "the" in headings)
_ARTICLE_RE = re.compile(r"\b(a|an|the)\s+", re.IGNORECASE)

# Filler adverbs/intensifiers
_FILLER_RE = re.compile(
    r"\b(just|really|basically|actually|simply|essentially|quite|"
    r"very|extremely|highly|totally|completely|absolutely|definitely|"
    r"certainly|obviously|clearly|naturally|literally|honestly|"
    r"in fact|as a matter of fact|for the most part|at the end of the day|"
    r"needless to say|it goes without saying that|"
    r"please note that|please be aware that|"
    r"it is important to note that|it is worth noting that|"
    r"it should be noted that)\s*,?\s*",
    re.IGNORECASE,
)

# Pleasantries and hedge openers
_PLEASANTRY_RE = re.compile(
    r"^(sure[!,.]?\s*|certainly[!,.]?\s*|of course[!,.]?\s*|"
    r"happy to\s+|glad to\s+|i('d| would) be happy to\s+|"
    r"i('d| would) be glad to\s+|"
    r"absolutely[!,.]?\s*|great[!,.]?\s*|"
    r"let me\s+help\s+you\s+(with\s+)?(that|this)[.!]?\s*|"
    r"i('ll| will) help you (with )?(that|this)[.!]?\s*)",
    re.IGNORECASE | re.MULTILINE,
)

# Verbose phrase → compact replacement
_PHRASE_MAP: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
    (re.compile(r"\bdue to the fact that\b", re.IGNORECASE), "because"),
    (re.compile(r"\bat this point in time\b", re.IGNORECASE), "now"),
    (re.compile(r"\bfor the purpose of\b", re.IGNORECASE), "for"),
    (re.compile(r"\bmake use of\b", re.IGNORECASE), "use"),
    (re.compile(r"\bin the event that\b", re.IGNORECASE), "if"),
    (re.compile(r"\bprior to\b", re.IGNORECASE), "before"),
    (re.compile(r"\bsubsequent to\b", re.IGNORECASE), "after"),
    (re.compile(r"\bwith the exception of\b", re.IGNORECASE), "except"),
    (re.compile(r"\bin spite of\b", re.IGNORECASE), "despite"),
    (re.compile(r"\bis able to\b", re.IGNORECASE), "can"),
    (re.compile(r"\bare able to\b", re.IGNORECASE), "can"),
    (re.compile(r"\bwas able to\b", re.IGNORECASE), "could"),
    (re.compile(r"\bhas the ability to\b", re.IGNORECASE), "can"),
    (re.compile(r"\bIt is recommended that you\b", re.IGNORECASE), ""),
    (re.compile(r"\bIt is recommended to\b", re.IGNORECASE), ""),
    (re.compile(r"\byou should\b", re.IGNORECASE), ""),
    (re.compile(r"\byou can\b", re.IGNORECASE), ""),
    (re.compile(r"\byou will need to\b", re.IGNORECASE), ""),
    (re.compile(r"\bwe will\b", re.IGNORECASE), "will"),
    (re.compile(r"\bwe can\b", re.IGNORECASE), "can"),
    (re.compile(r"\bplease (note|remember|keep in mind) that\b", re.IGNORECASE), "note:"),
    (re.compile(r"\bthe following\b", re.IGNORECASE), ""),
    (re.compile(r"\bthe above\b", re.IGNORECASE), "above"),
    (re.compile(r"\bimplementation\b", re.IGNORECASE), "impl"),
    (re.compile(r"\bconfiguration\b", re.IGNORECASE), "config"),
    (re.compile(r"\benvironment\b", re.IGNORECASE), "env"),
    (re.compile(r"\bdocumentation\b", re.IGNORECASE), "docs"),
    (re.compile(r"\bdirectory\b", re.IGNORECASE), "dir"),
    (re.compile(r"\brepository\b", re.IGNORECASE), "repo"),
    (re.compile(r"\bdependencies\b", re.IGNORECASE), "deps"),
    (re.compile(r"\bdependency\b", re.IGNORECASE), "dep"),
]

# Collapse 2+ blank lines → 1
_MULTI_BLANK_RE = re.compile(r"\n{3,}")

# Strip trailing whitespace per line
_TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)


def _compress_line(line: str) -> str:
    """Apply compression rules to a single prose line."""
    # Skip headings (preserve exactly)
    if re.match(r"^#{1,6}\s", line):
        return line
    # Skip horizontal rules
    if re.match(r"^[-*_]{3,}\s*$", line):
        return line
    # Skip table rows
    if "|" in line and line.strip().startswith("|"):
        return line

    # Apply phrase map first (order matters)
    for pattern, replacement in _PHRASE_MAP:
        line = pattern.sub(replacement, line)

    # Drop filler adverbs
    line = _FILLER_RE.sub("", line)

    # Drop articles — but only mid-sentence (not at start if it changes meaning)
    line = _ARTICLE_RE.sub(" ", line)

    # Drop pleasantry openers (whole-line match)
    line = _PLEASANTRY_RE.sub("", line)

    # Clean up double spaces from removals
    line = re.sub(r"  +", " ", line)
    line = line.strip()

    return line


def compress_text(text: str, preserve_frontmatter: bool = True) -> str:
    """Compress prose text. Returns compressed string."""
    # Split off YAML frontmatter
    frontmatter = ""
    body = text
    if preserve_frontmatter:
        fm_m = re.match(r"^---\n(.*?)\n---\n?", text, re.DOTALL)
        if fm_m:
            frontmatter = text[: fm_m.end()]
            body = text[fm_m.end():]

    # Protect code blocks, inline code, URLs
    body, protected = _extract_protected(body)

    # Compress line by line
    lines = body.split("\n")
    compressed_lines = [_compress_line(ln) for ln in lines]
    body = "\n".join(compressed_lines)

    # Restore protected zones
    body = _restore_protected(body, protected)

    # Collapse excess blank lines
    body = _MULTI_BLANK_RE.sub("\n\n", body)

    # Strip trailing whitespace
    body = _TRAILING_WS_RE.sub("", body)

    return frontmatter + body.lstrip("\n")


def compress_file(filepath: Path, dry_run: bool = False) -> dict:
    """Compress a file in-place. Returns stats dict."""
    from detect import should_compress

    if not should_compress(filepath):
        return {"skipped": True, "reason": "not natural language"}

    original = filepath.read_text(encoding="utf-8", errors="ignore")
    compressed = compress_text(original)

    orig_tokens = len(original.split())  # rough word count as proxy
    comp_tokens = len(compressed.split())
    reduction = (1 - comp_tokens / orig_tokens) * 100 if orig_tokens else 0

    if not dry_run:
        filepath.write_text(compressed, encoding="utf-8")

    return {
        "skipped": False,
        "original_words": orig_tokens,
        "compressed_words": comp_tokens,
        "reduction_pct": round(reduction, 1),
        "path": str(filepath),
    }


def compress_skill_content(skill_content: str) -> str:
    """Compress SKILL.md body for context injection. Strips frontmatter."""
    # Remove YAML frontmatter entirely (AI doesn't need it at runtime)
    body = re.sub(r"^---\n.*?\n---\n?", "", skill_content, flags=re.DOTALL)
    return compress_text(body, preserve_frontmatter=False)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Inline caveman text compressor")
    p.add_argument("filepath", nargs="?", help="File to compress in-place")
    p.add_argument("--text", help="Compress a string (prints result)")
    p.add_argument("--skill", help="Compress SKILL.md content and print (no write)")
    p.add_argument("--dry-run", action="store_true", help="Show stats without writing")
    p.add_argument("--stats", action="store_true", help="Show word count reduction")
    args = p.parse_args()

    if args.text:
        print(compress_text(args.text))
        return

    if args.skill:
        content = Path(args.skill).read_text(encoding="utf-8", errors="ignore")
        compressed = compress_skill_content(content)
        print(compressed)
        orig_w = len(content.split())
        comp_w = len(compressed.split())
        reduction = (1 - comp_w / orig_w) * 100 if orig_w else 0
        print(f"\n[{orig_w} → {comp_w} words, -{reduction:.0f}%]", file=sys.stderr)
        return

    if args.filepath:
        path = Path(args.filepath).resolve()
        stats = compress_file(path, dry_run=args.dry_run)
        if stats.get("skipped"):
            print(f"Skipped: {stats['reason']}")
        else:
            action = "Would compress" if args.dry_run else "Compressed"
            print(f"{action}: {stats['path']}")
            print(f"  {stats['original_words']} → {stats['compressed_words']} words (-{stats['reduction_pct']}%)")
        return

    p.print_help()


if __name__ == "__main__":
    main()
