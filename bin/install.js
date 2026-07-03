#!/usr/bin/env node
/**
 * Auto Skill Finder — Multi-agent installer
 * Wires hooks and config for: Claude Code, Cursor, Gemini CLI, OpenCode, Codex, Copilot, Cline
 *
 * Usage:
 *   node bin/install.js                  # auto-detect and install all found agents
 *   node bin/install.js --only claude    # install for Claude Code only
 *   node bin/install.js --uninstall      # remove all hooks and config
 *   node bin/install.js --list           # show detected agents
 */
"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");

const HOME = os.homedir();
const SKILL_ROOT = path.join(__dirname, "..");
const HOOKS_DIR = path.join(SKILL_ROOT, "hooks");
const CONFIG_DIR = path.join(SKILL_ROOT, "config");

const CLAUDE_CONFIG_DIR = process.env.CLAUDE_CONFIG_DIR || path.join(HOME, ".claude");
const XDG_CONFIG = process.env.XDG_CONFIG_HOME || path.join(HOME, ".config");

// ── Agent definitions ──────────────────────────────────────────────────────────

const AGENTS = [
  {
    id: "claude",
    label: "Claude Code",
    detect: () => fs.existsSync(path.join(CLAUDE_CONFIG_DIR, "settings.json")),
    install: installClaude,
    uninstall: uninstallClaude,
  },
  {
    id: "cursor",
    label: "Cursor",
    detect: () => fs.existsSync(path.join(HOME, ".cursor")),
    install: installCursor,
    uninstall: () => uninstallRuleFile(path.join(".cursor", "rules", "auto-skill-finder.mdc")),
  },
  {
    id: "gemini",
    label: "Gemini CLI",
    detect: () => fs.existsSync(path.join(HOME, ".gemini")) || fs.existsSync(path.join(XDG_CONFIG, "gemini")),
    install: installGemini,
    uninstall: uninstallGemini,
  },
  {
    id: "opencode",
    label: "OpenCode",
    detect: () => fs.existsSync(path.join(XDG_CONFIG, "opencode")),
    install: installOpenCode,
    uninstall: uninstallOpenCode,
  },
  {
    id: "codex",
    label: "OpenAI Codex",
    soft: true,
    detect: () => fs.existsSync(path.join(HOME, ".codex")),
    install: installCodex,
    uninstall: uninstallCodex,
  },
  {
    id: "cline",
    label: "Cline",
    soft: true,
    detect: () => fs.existsSync(path.join(process.cwd(), ".clinerules")),
    install: () => installRuleFile(path.join(".clinerules", "auto-skill-finder.md"), ruleContent()),
    uninstall: () => uninstallRuleFile(path.join(".clinerules", "auto-skill-finder.md")),
  },
];

// ── Helpers ────────────────────────────────────────────────────────────────────

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

function readJSON(p) {
  try { return JSON.parse(fs.readFileSync(p, "utf8")); } catch (_) { return {}; }
}

function writeJSON(p, obj) {
  ensureDir(path.dirname(p));
  fs.writeFileSync(p, JSON.stringify(obj, null, 2) + "\n", "utf8");
}

function ruleContent() {
  const skillMd = path.join(SKILL_ROOT, "SKILL.md");
  const agentsMd = path.join(SKILL_ROOT, "AGENTS.md");
  if (fs.existsSync(agentsMd)) return fs.readFileSync(agentsMd, "utf8");
  if (fs.existsSync(skillMd)) return fs.readFileSync(skillMd, "utf8");
  return "# Auto Skill Finder\nSee https://github.com/skills/auto-skill-finder";
}

function installRuleFile(relPath, content) {
  const full = path.join(process.cwd(), relPath);
  ensureDir(path.dirname(full));
  fs.writeFileSync(full, content, "utf8");
  console.log(`  Wrote ${full}`);
}

function uninstallRuleFile(relPath) {
  const full = path.join(process.cwd(), relPath);
  try { fs.unlinkSync(full); console.log(`  Removed ${full}`); } catch (_) {}
}

// ── Claude Code ────────────────────────────────────────────────────────────────

const HOOK_MARKER = "auto-skill-finder";

function installClaude() {
  const hooksDir = path.join(CLAUDE_CONFIG_DIR, "hooks");
  ensureDir(hooksDir);

  // Copy hooks
  const sessionHook = path.join(HOOKS_DIR, "SessionStart.js");
  const promptHook = path.join(HOOKS_DIR, "UserPromptSubmit.js");
  const destSession = path.join(hooksDir, "auto-skill-SessionStart.js");
  const destPrompt = path.join(hooksDir, "auto-skill-UserPromptSubmit.js");
  fs.copyFileSync(sessionHook, destSession);
  fs.copyFileSync(promptHook, destPrompt);
  console.log(`  Hooks → ${hooksDir}`);

  // Patch settings.json
  const settingsPath = path.join(CLAUDE_CONFIG_DIR, "settings.json");
  const settings = readJSON(settingsPath);

  if (!settings.hooks) settings.hooks = {};

  const sessionEntry = { matcher: HOOK_MARKER, hooks: [{ type: "command", command: `node "${destSession}"` }] };
  const promptEntry = { matcher: HOOK_MARKER, hooks: [{ type: "command", command: `node "${destPrompt}"` }] };

  if (!settings.hooks.SessionStart) settings.hooks.SessionStart = [];
  if (!settings.hooks.UserPromptSubmit) settings.hooks.UserPromptSubmit = [];

  // Remove old entries
  settings.hooks.SessionStart = settings.hooks.SessionStart.filter(h => !JSON.stringify(h).includes(HOOK_MARKER));
  settings.hooks.UserPromptSubmit = settings.hooks.UserPromptSubmit.filter(h => !JSON.stringify(h).includes(HOOK_MARKER));

  settings.hooks.SessionStart.push(sessionEntry);
  settings.hooks.UserPromptSubmit.push(promptEntry);

  writeJSON(settingsPath, settings);
  console.log(`  Patched ${settingsPath}`);
}

function uninstallClaude() {
  const settingsPath = path.join(CLAUDE_CONFIG_DIR, "settings.json");
  const settings = readJSON(settingsPath);
  if (settings.hooks) {
    for (const key of ["SessionStart", "UserPromptSubmit"]) {
      if (Array.isArray(settings.hooks[key])) {
        settings.hooks[key] = settings.hooks[key].filter(h => !JSON.stringify(h).includes(HOOK_MARKER));
      }
    }
  }
  writeJSON(settingsPath, settings);
  // Remove hook files
  const hooksDir = path.join(CLAUDE_CONFIG_DIR, "hooks");
  for (const f of ["auto-skill-SessionStart.js", "auto-skill-UserPromptSubmit.js"]) {
    try { fs.unlinkSync(path.join(hooksDir, f)); } catch (_) {}
  }
  console.log("  Claude Code: uninstalled");
}

// ── Cursor ─────────────────────────────────────────────────────────────────────

function installCursor() {
  const content = readFile(path.join(SKILL_ROOT, "SKILL.md")) || ruleContent();
  const mdc = `---
description: Auto Skill Finder — routes prompts to best skill + activates caveman mode
alwaysApply: true
---

${content}`;
  installRuleFile(path.join(".cursor", "rules", "auto-skill-finder.mdc"), mdc);
}

// ── Gemini CLI ─────────────────────────────────────────────────────────────────

function installGemini() {
  const extPath = path.join(XDG_CONFIG, "gemini", "extensions", "auto-skill-finder");
  ensureDir(extPath);

  // Copy GEMINI.md as context file
  const src = path.join(SKILL_ROOT, "GEMINI.md");
  const dst = path.join(extPath, "GEMINI.md");
  if (fs.existsSync(src)) fs.copyFileSync(src, dst);

  // Write gemini-extension.json
  const ext = {
    name: "auto-skill-finder",
    version: "2.0.0",
    description: "Auto-routes prompts to best installed skill + caveman mode",
    contextFileName: "GEMINI.md",
  };
  writeJSON(path.join(extPath, "gemini-extension.json"), ext);
  console.log(`  Gemini extension → ${extPath}`);
}

// ── OpenCode ───────────────────────────────────────────────────────────────────

function installOpenCode() {
  // Write AGENTS.md to opencode workspace
  const workspace = path.join(XDG_CONFIG, "opencode", "workspace");
  ensureDir(workspace);
  const src = path.join(SKILL_ROOT, "AGENTS.md");
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(workspace, "AGENTS.md"));
    console.log(`  OpenCode AGENTS.md → ${workspace}`);
  }
}

// ── Codex ──────────────────────────────────────────────────────────────────────

function installCodex() {
  const codexDir = path.join(HOME, ".codex");
  ensureDir(codexDir);
  // Append to system-prompt.md
  const sysPrompt = path.join(codexDir, "system-prompt.md");
  const content = "\n\n" + (readFile(path.join(SKILL_ROOT, "SKILL.md")) || "");
  const existing = readFile(sysPrompt) || "";
  if (!existing.includes("auto-skill-finder")) {
    fs.appendFileSync(sysPrompt, content, "utf8");
    console.log(`  Codex system-prompt → ${sysPrompt}`);
  }
}

function uninstallGemini() {
  const extPath = path.join(XDG_CONFIG, "gemini", "extensions", "auto-skill-finder");
  try {
    fs.rmSync(extPath, { recursive: true, force: true });
    console.log(`  Removed ${extPath}`);
  } catch (_) {}
}

function uninstallOpenCode() {
  const agentsMd = path.join(XDG_CONFIG, "opencode", "workspace", "AGENTS.md");
  try { fs.unlinkSync(agentsMd); console.log(`  Removed ${agentsMd}`); } catch (_) {}
}

function uninstallCodex() {
  const sysPrompt = path.join(HOME, ".codex", "system-prompt.md");
  try {
    const content = fs.readFileSync(sysPrompt, "utf8");
    // Remove the block we appended (from \n\n---\nname: auto-skill-finder onwards)
    const cleaned = content
      .replace(/\n{1,2}---\nname: auto-skill-finder[\s\S]*$/m, "")
      .replace(/\n{1,2}# Auto Skill Finder[\s\S]*$/m, "")
      .trimEnd();
    if (cleaned !== content.trimEnd()) {
      fs.writeFileSync(sysPrompt, cleaned + "\n", "utf8");
      console.log(`  Cleaned ${sysPrompt}`);
    } else {
      console.log(`  Codex: no auto-skill-finder block found in ${sysPrompt}`);
    }
  } catch (_) {}
}

function readFile(p) {
  try { return fs.readFileSync(p, "utf8"); } catch (_) { return null; }
}

// ── CLI ────────────────────────────────────────────────────────────────────────

const args = process.argv.slice(2);
const onlyAgent = args.find((_, i) => args[i - 1] === "--only");
const isUninstall = args.includes("--uninstall");
const isList = args.includes("--list");

if (isList) {
  console.log("Detected agents:");
  for (const agent of AGENTS) {
    const found = agent.detect();
    const soft = agent.soft ? " (soft)" : "";
    console.log(`  ${found ? "✓" : "✗"} ${agent.label}${soft}`);
  }
  process.exit(0);
}

for (const agent of AGENTS) {
  if (onlyAgent && agent.id !== onlyAgent) continue;
  if (!agent.detect() && !onlyAgent) continue;

  console.log(`${isUninstall ? "Uninstalling" : "Installing"}: ${agent.label}`);
  try {
    if (isUninstall) agent.uninstall();
    else agent.install();
  } catch (err) {
    console.error(`  Error: ${err.message}`);
  }
}

console.log("\nDone.");
