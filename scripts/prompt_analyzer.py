#!/usr/bin/env python3
"""
Prompt Analyzer — decomposes user prompts into structured intent + entities.
Used by skill_finder.py and hooks to enrich routing decisions.
"""
from __future__ import annotations

import re
import json
import argparse
from dataclasses import dataclass, asdict
from typing import Optional

# ── Entity patterns ────────────────────────────────────────────────────────────

LANG_PATTERNS = re.compile(
    r"\b(python|javascript|typescript|rust|go|golang|java|kotlin|swift|ruby|"
    r"php|c\+\+|cpp|c#|csharp|bash|shell|sql|html|css|yaml|json|toml)\b",
    re.IGNORECASE,
)

FRAMEWORK_PATTERNS = re.compile(
    r"\b(react|vue|angular|svelte|nextjs|next\.js|nuxt|fastapi|django|flask|"
    r"express|rails|laravel|spring|nestjs|tailwind|prisma|drizzle|supabase|"
    r"postgres|postgresql|mysql|sqlite|mongodb|redis|kafka|graphql|trpc)\b",
    re.IGNORECASE,
)

INTENT_KEYWORDS = {
    "build": ["build", "create", "make", "generate", "scaffold", "write", "implement", "add"],
    "fix": ["fix", "debug", "bug", "error", "broken", "failing", "wrong", "issue"],
    "refactor": ["refactor", "clean", "improve", "simplify", "reorganize", "restructure"],
    "review": ["review", "audit", "check", "inspect", "analyze", "assess"],
    "explain": ["explain", "what", "how", "why", "understand", "describe", "tell"],
    "optimize": ["optimize", "speed", "fast", "performance", "slow", "bottleneck"],
    "test": ["test", "spec", "unit", "integration", "coverage", "jest", "pytest"],
    "deploy": ["deploy", "release", "ci", "cd", "pipeline", "docker", "k8s"],
    "seo": ["seo", "search", "ranking", "keyword", "backlink", "sitemap", "meta"],
    "ui": ["ui", "ux", "design", "layout", "style", "css", "component", "frontend"],
    "data": ["data", "database", "schema", "migration", "query", "etl", "pipeline"],
    "security": ["security", "auth", "oauth", "jwt", "password", "permission", "vuln"],
    "api": ["api", "endpoint", "rest", "graphql", "webhook", "integration", "http"],
    "docs": ["docs", "documentation", "readme", "comment", "docstring", "wiki"],
}

CONSTRAINT_PATTERNS = re.compile(
    r"\b(without|no\s+\w+|must\s+be|must\s+not|only|avoid|except|skip|don['']t)\b",
    re.IGNORECASE,
)


@dataclass
class PromptAnalysis:
    raw: str
    core_intent: str
    intent_category: Optional[str]
    entities_langs: list[str]
    entities_frameworks: list[str]
    constraints: list[str]
    implicit_needs: list[str]
    keywords: list[str]


def analyze(prompt: str) -> PromptAnalysis:
    pl = prompt.lower()

    # Detect programming languages
    langs = list({m.group().lower() for m in LANG_PATTERNS.finditer(prompt)})

    # Detect frameworks/tools
    frameworks = list({m.group().lower() for m in FRAMEWORK_PATTERNS.finditer(prompt)})

    # Determine primary intent category
    intent_category: Optional[str] = None
    best_hit = 0
    for category, words in INTENT_KEYWORDS.items():
        hits = sum(1 for w in words if w in pl)
        if hits > best_hit:
            best_hit = hits
            intent_category = category

    # Extract constraints
    constraint_matches = CONSTRAINT_PATTERNS.findall(prompt)
    constraints = list(set(m.strip().lower() for m in constraint_matches))

    # Build implicit needs based on entities + intent
    implicit: list[str] = []
    if "react" in frameworks and intent_category == "build":
        implicit.append("component architecture")
    if langs and "test" not in pl and intent_category == "build":
        implicit.append("tests may be expected")
    if intent_category == "fix" and not langs:
        implicit.append("need to identify language from context")
    if "seo" in pl:
        implicit.append("search engine optimization context")

    # Top keywords (non-stopword content words)
    stopwords = {
        "a", "an", "the", "i", "to", "and", "or", "is", "it", "in",
        "of", "for", "with", "that", "this", "on", "be", "can", "do",
        "my", "me", "you", "we", "our",
    }
    words = [w.lower() for w in re.findall(r"\w{3,}", prompt)]
    keywords = [w for w in dict.fromkeys(words) if w not in stopwords][:10]

    # Core intent: first imperative sentence or first clause
    first_sentence = re.split(r"[.!?\n]", prompt.strip())[0].strip()
    core_intent = first_sentence[:120]

    return PromptAnalysis(
        raw=prompt,
        core_intent=core_intent,
        intent_category=intent_category,
        entities_langs=langs,
        entities_frameworks=frameworks,
        constraints=constraints,
        implicit_needs=implicit,
        keywords=keywords,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Prompt Analyzer")
    p.add_argument("prompt", help="Prompt to analyze")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    result = analyze(args.prompt)

    if args.json:
        print(json.dumps(asdict(result), indent=2))
        return

    print(f"Intent:      {result.core_intent}")
    print(f"Category:    {result.intent_category or 'unknown'}")
    print(f"Languages:   {', '.join(result.entities_langs) or 'none'}")
    print(f"Frameworks:  {', '.join(result.entities_frameworks) or 'none'}")
    print(f"Keywords:    {', '.join(result.keywords[:6])}")
    print(f"Constraints: {', '.join(result.constraints) or 'none'}")
    print(f"Implicit:    {', '.join(result.implicit_needs) or 'none'}")


if __name__ == "__main__":
    main()
