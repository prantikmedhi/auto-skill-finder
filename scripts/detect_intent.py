#!/usr/bin/env python3
"""
Intent Detector — classify a prompt as 'code' or 'chat'.

Code = writing, debugging, reviewing, or reasoning about software.
Chat = explanation, planning, writing, Q&A, creative, general assistance.

No ML required. Fast rule-based classifier. Used by hooks to pick
caveman-code vs caveman-chat response mode.

Usage:
    python detect_intent.py "fix the auth bug in my middleware"
    # → code

    python detect_intent.py "explain how JWT works"
    # → chat  (explanation, not implementation)

    python detect_intent.py --json "refactor this to use async/await"
    # → {"intent": "code", "confidence": 0.92, "signals": [...]}
"""
from __future__ import annotations

import re
import json
import argparse
from dataclasses import dataclass, asdict

# ── Code signals ──────────────────────────────────────────────────────────────

CODE_VERBS = re.compile(
    r"\b(fix|debug|implement|build|refactor|write|create|add|remove|delete|"
    r"update|migrate|deploy|test|review|optimize|rewrite|generate|scaffold|"
    r"compile|run|execute|install|configure|parse|serialize|deserialize|"
    r"import|export|init|setup|wire|hook|patch|merge|commit|push|pull|"
    r"lint|format|typecheck|validate|mock|stub|seed|encrypt|hash)\b",
    re.IGNORECASE,
)

CODE_NOUNS = re.compile(
    r"\b(function|class|method|module|component|hook|middleware|handler|"
    r"endpoint|route|controller|model|schema|migration|query|index|cache|"
    r"api|sdk|cli|script|dockerfile|ci|pipeline|workflow|action|job|"
    r"variable|constant|type|interface|enum|struct|trait|impl|"
    r"database|db|sql|orm|repo|repository|service|store|context|"
    r"bug|error|exception|stacktrace|traceback|crash|segfault|"
    r"test|spec|suite|fixture|mock|coverage|assertion|"
    r"regex|algorithm|data structure|heap|queue|tree|graph|"
    r"async|await|promise|callback|thread|process|goroutine|"
    r"loop|recursion|iterator|generator|closure|lambda|"
    r"pr|pull request|diff|branch|commit|merge conflict|"
    r"package|dependency|dep|npm|pip|cargo|go mod|poetry|"
    r"env|config|secret|token|key|credential|auth|oauth|jwt|"
    r"docker|kubernetes|k8s|terraform|ansible|helm|"
    r"react|vue|angular|svelte|nextjs|fastapi|django|flask|express|rails)\b",
    re.IGNORECASE,
)

FILE_EXTENSION_RE = re.compile(
    r"\b\w+\.(py|js|ts|tsx|jsx|go|rs|rb|java|kt|swift|c|cpp|h|cs|php|"
    r"sql|sh|bash|zsh|yaml|yml|toml|json|md|dockerfile|lock)\b",
    re.IGNORECASE,
)

CODE_BLOCK_RE = re.compile(r"```|`[^`\n]{3,}`")

ERROR_SIGNAL_RE = re.compile(
    r"(error:|exception:|traceback|stack trace|line \d+|undefined|"
    r"null pointer|segfault|panic:|fatal:|warning:|cannot find|"
    r"module not found|import error|syntax error|type error|"
    r"404|500|503|ENOENT|ECONNREFUSED)",
    re.IGNORECASE,
)

PATH_RE = re.compile(r"[./\\]\w[\w./\\-]{2,}")

# ── Chat signals ──────────────────────────────────────────────────────────────

CHAT_VERBS = re.compile(
    r"\b(explain|describe|summarize|tell|what is|what are|what does|"
    r"how does|why does|when should|who|define|compare|contrast|"
    r"list|outline|suggest|recommend|advise|help me understand|"
    r"translate|proofread|draft|write (an?|the) (email|letter|essay|post|"
    r"article|report|summary|plan|document|proposal|pitch|outline))\b",
    re.IGNORECASE,
)

CHAT_TOPICS = re.compile(
    r"\b(concept|theory|idea|strategy|approach|best practice|"
    r"difference between|pros and cons|tradeoffs?|comparison|"
    r"history|background|overview|introduction|beginner|basics|"
    r"career|interview|resume|salary|job|team|meeting|email|"
    r"design decision|architecture decision|should i use|which is better)\b",
    re.IGNORECASE,
)

# ── Scoring ───────────────────────────────────────────────────────────────────

@dataclass
class IntentResult:
    intent: str          # "code" | "chat"
    confidence: float    # 0.0 - 1.0
    code_score: int
    chat_score: int
    signals: list[str]


def detect(prompt: str) -> IntentResult:
    signals: list[str] = []
    code_score = 0
    chat_score = 0

    # ── Code signals ──────────────────────────────────────────
    if CODE_BLOCK_RE.search(prompt):
        code_score += 8
        signals.append("code_block")

    verb_hits = CODE_VERBS.findall(prompt)
    if verb_hits:
        code_score += min(len(verb_hits) * 3, 12)
        signals.append(f"code_verbs={','.join(set(v.lower() for v in verb_hits[:3]))}")

    noun_hits = CODE_NOUNS.findall(prompt)
    if noun_hits:
        code_score += min(len(noun_hits) * 2, 10)
        signals.append(f"code_nouns={','.join(set(n.lower() for n in noun_hits[:3]))}")

    if FILE_EXTENSION_RE.search(prompt):
        code_score += 5
        signals.append("file_extension")

    if ERROR_SIGNAL_RE.search(prompt):
        code_score += 8
        signals.append("error_signal")

    if PATH_RE.search(prompt):
        code_score += 3
        signals.append("file_path")

    # ── Chat signals ──────────────────────────────────────────
    chat_verb_hits = CHAT_VERBS.findall(prompt)
    if chat_verb_hits:
        chat_score += min(len(chat_verb_hits) * 4, 16)
        signals.append(f"chat_verbs={','.join(set(str(v[0] if isinstance(v, tuple) else v).lower() for v in chat_verb_hits[:3]))}")

    topic_hits = CHAT_TOPICS.findall(prompt)
    if topic_hits:
        chat_score += min(len(topic_hits) * 3, 9)
        signals.append(f"chat_topics={','.join(set(t.lower() for t in topic_hits[:2]))}")

    # ── Short pure-question heuristic ─────────────────────────
    words = prompt.strip().split()
    if len(words) <= 10 and prompt.strip().endswith("?"):
        chat_score += 5
        signals.append("short_question")

    # ── Resolve ───────────────────────────────────────────────
    total = code_score + chat_score or 1
    if code_score >= chat_score:
        intent = "code"
        confidence = round(code_score / total, 2)
    else:
        intent = "chat"
        confidence = round(chat_score / total, 2)

    # Boost confidence if one side dominates
    if abs(code_score - chat_score) < 3:
        confidence = max(0.5, confidence - 0.1)  # ambiguous

    return IntentResult(
        intent=intent,
        confidence=confidence,
        code_score=code_score,
        chat_score=chat_score,
        signals=signals,
    )


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Detect code vs chat intent")
    p.add_argument("prompt", help="Prompt to classify")
    p.add_argument("--json", action="store_true", help="Output JSON")
    args = p.parse_args()

    result = detect(args.prompt)

    if args.json:
        print(json.dumps(asdict(result), indent=2))
        return

    print(f"Intent:     {result.intent}")
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Code score: {result.code_score}")
    print(f"Chat score: {result.chat_score}")
    print(f"Signals:    {', '.join(result.signals) or 'none'}")


if __name__ == "__main__":
    main()
