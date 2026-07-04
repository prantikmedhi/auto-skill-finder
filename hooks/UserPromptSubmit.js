#!/usr/bin/env node
/**
 * Auto Skill Finder — UserPromptSubmit hook
 *
 * Per prompt:
 *   1. Detect intent (code vs chat) → pick caveman mode
 *   2. Find best matching installed skill
 *   3. Inline-compress skill content (saves tokens)
 *   4. Inject caveman mode rules + skill content as system context
 */
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");
const { spawnSync } = require("child_process");

const CLAUDE_CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), ".claude");
const HOME = os.homedir();

// Find the auto-skill-finder install directory (hook may be installed to ~/.claude/hooks/)
function findInstallDir() {
  const candidates = [
    path.join(__dirname, ".."),                          // dev: hooks/../
    path.join(HOME, ".auto-skill-finder"),               // one-liner install
    path.join(HOME, "skills", "auto-skill-finder"),      // ~/skills/ location
    path.join(HOME, ".claude", "skills", "auto-skill-finder"),
  ];
  if (process.env.AUTO_SKILL_DIR) candidates.unshift(process.env.AUTO_SKILL_DIR);
  // Prefer dir that has detect_intent.py (newest feature marker)
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, "scripts", "detect_intent.py"))) return dir;
  }
  // Fallback: any dir with skill_finder.py
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, "scripts", "skill_finder.py"))) return dir;
  }
  return candidates[0];
}

const INSTALL_DIR = findInstallDir();
const SCRIPTS = path.join(INSTALL_DIR, "scripts");
const SKILL_FINDER    = path.join(SCRIPTS, "skill_finder.py");
const DETECT_INTENT   = path.join(SCRIPTS, "detect_intent.py");
const INLINE_COMPRESS = path.join(SCRIPTS, "inline_compress.py");
const SKILLS_DIR      = path.join(INSTALL_DIR, "skills");

// ── Read prompt from stdin ─────────────────────────────────────────────────────

let input = "";
try { input = fs.readFileSync("/dev/stdin", "utf8"); } catch (_) {}

let prompt = "";
try {
  const parsed = JSON.parse(input);
  prompt = parsed.prompt || parsed.message || parsed.input || "";
} catch (_) { prompt = input.trim(); }

if (!prompt) process.exit(0);

// ── Python ─────────────────────────────────────────────────────────────────────

function findPython() {
  for (const cmd of ["python3", "python"]) {
    try {
      const r = spawnSync(cmd, ["--version"], { timeout: 2000 });
      if (r.status === 0) return cmd;
    } catch (_) {}
  }
  return null;
}

const py = findPython();

// ── Intent detection ───────────────────────────────────────────────────────────

function detectIntent(prompt) {
  if (py && fs.existsSync(DETECT_INTENT)) {
    try {
      const r = spawnSync(py, [DETECT_INTENT, "--json", prompt], { timeout: 3000, encoding: "utf8" });
      if (r.status === 0 && r.stdout) {
        const result = JSON.parse(r.stdout);
        return result.intent; // "code" | "chat"
      }
    } catch (_) {}
  }

  // Inline JS fallback
  const pl = prompt.toLowerCase();
  const codeSignals = [
    /```/, /\.(py|js|ts|go|rs|rb|java|sql|sh)\b/,
    /\b(fix|debug|implement|refactor|test|deploy|compile|function|class|api|bug|error|stacktrace|migration|schema|endpoint|hook|middleware)\b/,
  ];
  const hits = codeSignals.filter(re => re.test(pl)).length;
  return hits >= 2 ? "code" : "chat";
}

const intent = detectIntent(prompt);

// ── Caveman mode anchors ───────────────────────────────────────────────────────

const CAVEMAN_CHAT_ANCHOR = `\
Respond terse like smart caveman. All technical substance stay. Only fluff die. \
Drop articles/filler/pleasantries/hedging. Fragments OK. Persist until "stop caveman".`;

const PONYTAIL_CODE_ANCHOR = `\
You are a lazy senior developer. Lazy means efficient, not careless. \
The best code is the code never written. Persist until "stop ponytail".

PONYTAIL CODE MODE ACTIVE. The ladder — stop at first rung that holds:
1. Needs to exist at all? (YAGNI)
2. Already in this codebase? Reuse it.
3. Stdlib does it? Use it.
4. Native platform feature covers it? Use it.
5. Installed dependency solves it? Use it. Never add new one for few lines.
6. Can be one line? One line.
7. Only then: minimum code that works.
Bug fix = root cause, not symptom. Shortest working diff wins — after understanding problem fully.
Output: code first, then max 3 lines — what skipped, when to add.`;

// Mode name per intent: code → ponytail-code, chat → caveman-chat
const MODE_NAME = { code: "ponytail-code", chat: "caveman-chat" };

// ── Mode skill bodies ──────────────────────────────────────────────────────────

function loadModeSkill(mode) {
  const p = path.join(SKILLS_DIR, MODE_NAME[mode], "SKILL.md");
  try {
    const content = fs.readFileSync(p, "utf8");
    return content.replace(/^---[\s\S]*?---\n?/, "").trim();
  } catch (_) { return ""; }
}

// ── Skill discovery ────────────────────────────────────────────────────────────

function runPythonFinder(prompt) {
  if (!py || !fs.existsSync(SKILL_FINDER)) return null;
  try {
    const r = spawnSync(py, [SKILL_FINDER, "--prompt", prompt, "--json"], { timeout: 5000, encoding: "utf8" });
    if (r.status !== 0 || !r.stdout) return null;
    const data = JSON.parse(r.stdout);
    const top = data.candidate_skills && data.candidate_skills[0];
    if (!top || top.score < 4) return null;
    return {
      selected_skill: top.skill_name,
      selected_skill_path: top.path,
      score: top.score,
    };
  } catch (_) {}
  return null;
}

function inlineScore(prompt, skillContent) {
  const pl = prompt.toLowerCase();
  const name_m = skillContent.match(/^name:\s*(.+)/m);
  if (!name_m) return 0;
  let score = 0;
  const name = name_m[1].trim().toLowerCase();
  if (pl.includes(name.replace(/-/g, " ")) || pl.includes(name)) score += 10;
  const trig_m = skillContent.match(/^triggers:\s*\[(.+?)\]/m);
  if (trig_m) {
    for (const t of trig_m[1].split(",").map(t => t.trim().replace(/['"]/g, "").toLowerCase())) {
      if (pl.includes(t)) { score += 5; break; }
    }
  }
  const stop = new Set(["a","an","the","is","to","for","with","and","or","in","of","it"]);
  const pw = new Set(pl.split(/\W+/).filter(w => w.length > 2 && !stop.has(w)));
  const desc_m = skillContent.match(/^description:\s*>?\n?([\s\S]+?)(?=\n\w|---)/m);
  const dw = new Set((desc_m ? desc_m[1] : "").toLowerCase().split(/\W+/).filter(w => w.length > 2 && !stop.has(w)));
  let overlap = 0; for (const w of pw) if (dw.has(w)) overlap++;
  score += Math.min(overlap, 7);
  return score;
}

function scanSkillsInline(prompt) {
  const dirs = [
    path.join(CLAUDE_CONFIG_DIR, "skills"),
    path.join(CLAUDE_CONFIG_DIR, "plugins"),
    path.join(HOME, "skills"),
  ];
  let best = null, bestScore = 0;
  for (const dir of dirs) {
    if (!fs.existsSync(dir)) continue;
    try {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (!entry.isDirectory()) continue;
        const skillPath = path.join(dir, entry.name, "SKILL.md");
        if (!fs.existsSync(skillPath)) continue;
        let content;
        try { content = fs.readFileSync(skillPath, "utf8"); } catch (_) { continue; }
        const score = inlineScore(prompt, content);
        if (score > bestScore) { bestScore = score; best = { path: skillPath, score, content, name: entry.name }; }
      }
    } catch (_) {}
  }
  return bestScore >= 4 ? best : null;
}

// ── Inline compress ────────────────────────────────────────────────────────────

function compressContent(content) {
  if (!py || !fs.existsSync(INLINE_COMPRESS)) return content;
  const tmp = path.join(os.tmpdir(), `asf-skill-${process.pid}.md`);
  try {
    fs.writeFileSync(tmp, content, "utf8");
    const r = spawnSync(py, [INLINE_COMPRESS, "--skill", tmp], { timeout: 4000, encoding: "utf8" });
    if (r.status === 0 && r.stdout && r.stdout.trim()) return r.stdout.trim();
  } catch (_) {}
  finally { try { fs.unlinkSync(tmp); } catch (_) {} }
  return content;
}

// ── Status log (stderr → visible in hook UI, not injected into AI) ─────────────

function status(step, detail = "") {
  const line = detail ? `  ${step}: ${detail}` : `  ${step}`;
  process.stderr.write(line + "\n");
}

// ── Assemble output ────────────────────────────────────────────────────────────

process.stderr.write("⚡ auto-skill-finder\n");

const parts = [];

// 1. Mode anchor (code → ponytail, chat → caveman)
status("intent", intent);
status("mode", MODE_NAME[intent]);
parts.push(intent === "code" ? PONYTAIL_CODE_ANCHOR : CAVEMAN_CHAT_ANCHOR);

// 2. Mode skill body (ponytail-code or caveman-chat rules)
const modeSkillBody = loadModeSkill(intent);
if (modeSkillBody) {
  const compressed = compressContent(modeSkillBody);
  const saved = modeSkillBody.length - compressed.length;
  status("rules", `${MODE_NAME[intent]} loaded (${saved > 0 ? `-${saved}ch` : "no change"})`);
  parts.push(`[MODE: ${MODE_NAME[intent]}]\n${compressed}`);
} else {
  status("rules", `${MODE_NAME[intent]} (built-in anchor only)`);
}

// 3. Best matching installed skill
let selectedSkillContent = "";
let selectedSkillName = "";
let selectedSkillScore = 0;

status("scanning", "installed skills…");
const finderResult = runPythonFinder(prompt);
if (finderResult && finderResult.selected_skill_path) {
  try {
    selectedSkillContent = fs.readFileSync(finderResult.selected_skill_path, "utf8");
    selectedSkillName = finderResult.selected_skill || "";
    selectedSkillScore = finderResult.score || 0;
  } catch (_) {}
} else {
  const match = scanSkillsInline(prompt);
  if (match) {
    selectedSkillContent = match.content;
    selectedSkillName = match.name;
    selectedSkillScore = match.score;
  }
}

// Mode skills already injected in step 2 — don't double-inject via auto-skill
const MODE_SKILLS = new Set(["caveman-code", "caveman-chat", "ponytail-code", "caveman", "ponytail"]);
if (MODE_SKILLS.has(selectedSkillName)) {
  selectedSkillContent = "";
  selectedSkillName = "";
}

if (selectedSkillContent && selectedSkillName) {
  const rawBody = selectedSkillContent.replace(/^---[\s\S]*?---\n?/, "").trim();
  const before = rawBody.length;
  const body = compressContent(rawBody);
  const pct = Math.round((1 - body.length / before) * 100);
  status("skill", `${selectedSkillName} (score:${selectedSkillScore}) → compressed ${pct}%`);
  parts.push(`[AUTO-SKILL: ${selectedSkillName}]\n${body}`);
} else {
  status("skill", "no match — general caveman mode");
}

status("done", `${parts.length} context blocks injected`);

process.stdout.write(parts.join("\n\n"));
