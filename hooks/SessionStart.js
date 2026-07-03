#!/usr/bin/env node
/**
 * Auto Skill Finder — SessionStart hook
 * Writes caveman-active flag and emits caveman rules as system context.
 * Claude Code injects SessionStart stdout as a hidden system prompt.
 */
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");

const CLAUDE_CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
const FLAG_PATH = path.join(CLAUDE_CONFIG_DIR, ".caveman-active");

function safeWriteFlag(flagPath, content) {
  try {
    const dir = path.dirname(flagPath);
    const stat = fs.lstatSync(flagPath).isSymbolicLink();
    if (stat) return; // refuse symlink
  } catch (_) { /* doesn't exist yet — ok */ }
  try {
    fs.mkdirSync(path.dirname(flagPath), { recursive: true });
    fs.writeFileSync(flagPath, content, { mode: 0o600, flag: "w" });
  } catch (_) { /* silent fail — never block session */ }
}

safeWriteFlag(FLAG_PATH, "full");

// Emit caveman rules as system context (Claude Code injects this invisibly)
const CAVEMAN_RULES = `
Respond terse like smart caveman. All technical substance stay. Only fluff die.

ACTIVE EVERY RESPONSE. No revert. Off only: "stop caveman" / "normal mode".

Drop: articles (a/an/the), filler (just/really/basically/actually), pleasantries (sure/certainly/of course/happy to), hedging. Fragments OK. Technical terms exact. Code blocks unchanged. Errors quoted exact.

Pattern: [thing] [action] [reason]. [next step].

AUTO-SKILL-FINDER ACTIVE: On every prompt, mentally scan available skills in ~/.claude/skills/, ~/.claude/plugins/, ~/skills/ and route to best match (score ≥ 5). Caveman stays on through any skill execution.
`.trim();

process.stdout.write(CAVEMAN_RULES);
