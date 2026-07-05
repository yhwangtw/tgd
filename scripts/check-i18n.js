#!/usr/bin/env node
/**
 * check-i18n.js
 *
 * Guards the landing page's translations the same way check-readme-parity.js
 * guards the READMEs. docs/index.html holds English defaults in the markup
 * (data-i18n attributes) and zh/ja/de string dictionaries in an inline I18N
 * object. A key that exists in the markup but is missing from a dictionary
 * silently falls back to English — invisible drift. This makes it fail CI.
 *
 * Checks, per language (zh, ja, de):
 *   1. Every data-i18n key in the markup exists in the dictionary.
 *   2. Every dictionary key exists in the markup (no orphaned strings).
 *
 * Usage: node scripts/check-i18n.js
 * Exit codes: 0 = in sync, 1 = drift found
 */

const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'docs', 'index.html'), 'utf8');

const domKeys = new Set([...html.matchAll(/data-i18n="([^"]+)"/g)].map((m) => m[1]));

// isolate each language block inside the I18N object literal
const langs = ['zh', 'ja', 'de'];
let failed = false;

for (const lang of langs) {
  const block = html.match(new RegExp(`\\n  ${lang}: \\{([\\s\\S]*?)\\n  \\}`));
  if (!block) {
    console.error(`✗ ${lang}: dictionary block not found in I18N`);
    failed = true;
    continue;
  }
  const dictKeys = new Set([...block[1].matchAll(/"([a-z0-9.]+)":/g)].map((m) => m[1]));

  const missing = [...domKeys].filter((k) => !dictKeys.has(k));
  const orphaned = [...dictKeys].filter((k) => !domKeys.has(k));

  if (missing.length) {
    console.error(`✗ ${lang}: missing translations (will silently fall back to English): ${missing.join(', ')}`);
    failed = true;
  }
  if (orphaned.length) {
    console.error(`✗ ${lang}: orphaned dictionary keys (no matching element): ${orphaned.join(', ')}`);
    failed = true;
  }
  if (!missing.length && !orphaned.length) {
    console.log(`✓ ${lang}: ${dictKeys.size} keys, fully in sync with ${domKeys.size} markup keys`);
  }
}

if (failed) {
  console.error('\n❌ i18n check FAILED — sync docs/index.html dictionaries with its data-i18n keys');
  process.exit(1);
}
console.log(`\n✅ i18n OK — ${domKeys.size} keys × ${langs.length} languages`);
