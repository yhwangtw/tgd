#!/usr/bin/env node
/**
 * check-readme-parity.js
 *
 * Guards against translation drift between the four READMEs. The 28-vs-29
 * skill-count bugs, missing skill table rows, and missing sections that
 * accumulated in zh-TW/ja/de all belong to one failure class: the
 * translations are maintained by hand and nothing verified them against
 * English or against the skills/ directory. This script makes that class
 * of drift fail CI.
 *
 * Checks, per README (README.md, README.zh-TW.md, README.ja.md, README.de.md):
 *   1. Every directory in skills/ is linked exactly once
 *      (skills/<name>/SKILL.md), and no nonexistent skill is linked.
 *   2. The number of top-level "## " sections (outside fenced code blocks)
 *      matches the English README.
 *
 * Usage: node scripts/check-readme-parity.js
 * Exit codes: 0 = parity OK, 1 = drift found
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const READMES = ['README.md', 'README.zh-TW.md', 'README.ja.md', 'README.de.md'];

const skills = fs
  .readdirSync(path.join(ROOT, 'skills'), { withFileTypes: true })
  .filter((e) => e.isDirectory())
  .map((e) => e.name)
  .sort();

function stripFencedCode(text) {
  // remove ``` blocks so code samples don't count as headings/links
  return text.replace(/^```[\s\S]*?^```/gm, '');
}

let failed = false;
const fail = (msg) => {
  failed = true;
  console.error(`  ✗ ${msg}`);
};

const headingCounts = {};

for (const name of READMES) {
  const file = path.join(ROOT, name);
  console.log(`\n${name}`);
  if (!fs.existsSync(file)) {
    fail('file missing');
    continue;
  }
  const raw = fs.readFileSync(file, 'utf8');
  const text = stripFencedCode(raw);

  // 1. skill link parity against skills/
  const linked = [...text.matchAll(/skills\/(tgd-[a-z-]+)\/SKILL\.md/g)].map((m) => m[1]);
  const linkedSet = new Set(linked);
  for (const s of skills) {
    if (!linkedSet.has(s)) fail(`skill not linked: ${s}`);
  }
  for (const s of linkedSet) {
    if (!skills.includes(s)) fail(`links nonexistent skill: ${s}`);
  }
  if (!failed) console.log(`  ✓ all ${skills.length} skills linked`);

  // 2. top-level section count (outside code fences)
  const headings = (text.match(/^## /gm) || []).length;
  headingCounts[name] = headings;
  console.log(`  · ${headings} top-level sections`);
}

const en = headingCounts['README.md'];
for (const name of READMES.slice(1)) {
  if (headingCounts[name] !== undefined && headingCounts[name] !== en) {
    console.error(
      `\n  ✗ ${name} has ${headingCounts[name]} top-level sections, English has ${en} — a section is missing or extra`
    );
    failed = true;
  }
}

if (failed) {
  console.error('\n❌ README parity check FAILED — sync the translations with README.md');
  process.exit(1);
}
console.log(`\n✅ README parity OK — ${READMES.length} files, ${skills.length} skills each, ${en} sections each`);
