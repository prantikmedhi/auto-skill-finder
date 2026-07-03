#!/usr/bin/env node
/**
 * Auto Skill Finder — UserPromptSubmit hook
 * Runs on every user prompt. Finds best matching skill and injects it +
 * caveman reinforcement into hookSpecificOutput (appended as system context).
 */
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");
const { execFileSync, spawnSync } = require("child_process");

const CLAUDE_CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
const HOME = os.homedir();
const SKILL_FINDER = path.join(__dirname, "..", "scripts", "skill_finder.py");
const INLINE_COMPRESS = path.join(__dirname, "..", "scripts", "inline_compress.py");

// ── Read prompt from stdin ─────────────────────────────────────────────────────

let input = "";
try {
  input = fs.readFileSync("/dev/stdin", "utf8");
} catch (_) {}

let prompt = "";
try {
  const parsed = JSON.parse(input);
  prompt = parsed.prompt || parsed.message || parsed.input || "";
} catch (_) {
  prompt = input.trim();
}

// ── Find Python ────────────────────────────────────────────────────────────────

function findPython() {
  for (const cmd of ["python3", "python"]) {
    try {
      const r = spawnSync(cmd, ["--version"], { timeout: 2000 });
      if (r.status === 0) return cmd;
    } catch (_) {}
  }
  return null;
}

// ── Skill discovery ────────────────────────────────────────────────────────────

function runPythonFinder(py, prompt) {
  try {
    const result = spawnSync(
      py,
      [SKILL_FINDER, "--prompt", prompt, "--json"],
      { timeout: 5000, encoding: "utf8" }
    );
    if (result.status === 0 && result.stdout) {
      return JSON.parse(result.stdout);
    }
  } catch (_) {}
  return null;
}

function inlineScore(prompt, skillContent) {
  const pl = prompt.toLowerCase();
  const name_m = skillContent.match(/^name:\s*(.+)/m);
  const desc_m = skillContent.match(/^description:\s*>?\n?([\s\S]+?)(?=\n\w|---)/m);
  const trig_m = skillContent.match(/^triggers:\s*\[(.+?)\]/m);

  if (!name_m) return 0;
  const name = name_m[1].trim().toLowerCase();
  let score = 0;
  if (pl.includes(name.replace(/-/g, " ")) || pl.includes(name)) score += 10;
  if (trig_m) {
    const triggers = trig_m[1].split(",").map(t => t.trim().replace(/['"]/g, "").toLowerCase());
    for (const t of triggers) {
      if (pl.includes(t) && score < 25) score += 5;
    }
  }
  const stopwords = new Set(["a","an","the","is","to","for","with","and","or","in","of","it"]);
  const promptWords = new Set(pl.split(/\W+/).filter(w => w.length > 2 && !stopwords.has(w)));
  const descWords = new Set((desc_m ? desc_m[1] : "").toLowerCase().split(/\W+/).filter(w => w.length > 2 && !stopwords.has(w)));
  let overlap = 0;
  for (const w of promptWords) if (descWords.has(w)) overlap++;
  score += Math.min(overlap, 7);
  return score;
}

function scanSkillsInline(prompt) {
  const skillDirs = [
    path.join(CLAUDE_CONFIG_DIR, "skills"),
    path.join(CLAUDE_CONFIG_DIR, "plugins"),
    path.join(HOME, "skills"),
  ];

  let best = null;
  let bestScore = 0;

  for (const dir of skillDirs) {
    if (!fs.existsSync(dir)) continue;
    try {
      const entries = fs.readdirSync(dir, { withFileTypes: true });
      for (const entry of entries) {
        if (!entry.isDirectory()) continue;
        const skillPath = path.join(dir, entry.name, "SKILL.md");
        if (!fs.existsSync(skillPath)) continue;
        let content;
        try { content = fs.readFileSync(skillPath, "utf8"); } catch (_) { continue; }
        const score = inlineScore(prompt, content);
        if (score > bestScore) {
          bestScore = score;
          best = { path: skillPath, score, content, name: entry.name };
        }
      }
    } catch (_) {}
  }

  return bestScore >= 5 ? best : null;
}

// ── Main ───────────────────────────────────────────────────────────────────────

if (!prompt) {
  process.exit(0);
}

const CAVEMAN_ANCHOR = "Respond terse like smart caveman. All technical substance stay. Only fluff die. Drop articles/filler/pleasantries. Fragments OK. Persist until 'stop caveman'.";

let selectedSkillContent = "";
let selectedSkillName = "";

const py = findPython();
if (py && fs.existsSync(SKILL_FINDER)) {
  const result = runPythonFinder(py, prompt);
  if (result && result.selected_skill_path) {
    try {
      selectedSkillContent = fs.readFileSync(result.selected_skill_path, "utf8");
      selectedSkillName = result.selected_skill || "";
    } catch (_) {}
  }
} else {
  // Fallback: inline JS scanning
  const match = scanSkillsInline(prompt);
  if (match) {
    selectedSkillContent = match.content;
    selectedSkillName = match.name;
  }
}

// Compress skill content before injecting (saves tokens)
function compressSkillContent(py, content) {
  if (!py || !fs.existsSync(INLINE_COMPRESS)) return content;
  const os = require("os");
  const tmp = path.join(os.tmpdir(), `asf-skill-${process.pid}.md`);
  try {
    fs.writeFileSync(tmp, content, "utf8");
    const r = spawnSync(py, [INLINE_COMPRESS, "--skill", tmp], {
      timeout: 4000,
      encoding: "utf8",
    });
    if (r.status === 0 && r.stdout && r.stdout.trim()) return r.stdout.trim();
  } catch (_) {}
  finally {
    try { fs.unlinkSync(tmp); } catch (_) {}
  }
  return content;
}

// Build hook output
const parts = [CAVEMAN_ANCHOR];

if (selectedSkillContent && selectedSkillName) {
  // Strip frontmatter, then inline-compress before injecting
  const rawBody = selectedSkillContent.replace(/^---[\s\S]*?---\n?/, "").trim();
  const body = py ? compressSkillContent(py, rawBody) : rawBody;
  parts.push(`\n[AUTO-SKILL: ${selectedSkillName}]\n${body}`);
}

const output = {
  hookSpecificOutput: parts.join("\n\n"),
};

process.stdout.write(JSON.stringify(output));
