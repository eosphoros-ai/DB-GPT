#!/usr/bin/env node
/**
 * Locale parity check for connector.* keys.
 *
 * Why a regex parser instead of `import`?
 *   The locale files are `.ts` and Node can't natively import TypeScript without
 *   a transpiler. Adding a TS loader for one tiny script is overkill. The locale
 *   files are flat key/value records, so a line-based regex is sufficient and
 *   has no extra runtime cost. If the locale shape changes to nested objects,
 *   swap this for `tsx`/`esbuild-register` or a Node `--experimental-loader`.
 *
 * Exits non-zero on mismatch so CI can gate on it.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

const EN_PATH = path.join(ROOT, 'locales/en/common.ts');
const ZH_PATH = path.join(ROOT, 'locales/zh/common.ts');

const PREFIX = 'connector.';
// Captures keys of the form `'connector.xxx.yyy': '...',`.
// Allows single OR double-quoted keys; matches anywhere on the line.
const KEY_RE = /['"](connector\.[a-zA-Z0-9_.]+)['"]\s*:/g;

function extractKeys(filePath) {
  const src = fs.readFileSync(filePath, 'utf8');
  const keys = new Set();
  let m;
  while ((m = KEY_RE.exec(src)) !== null) {
    keys.add(m[1]);
  }
  return keys;
}

const enKeys = extractKeys(EN_PATH);
const zhKeys = extractKeys(ZH_PATH);

const missingInZh = [...enKeys].filter(k => !zhKeys.has(k));
const missingInEn = [...zhKeys].filter(k => !enKeys.has(k));

if (missingInZh.length || missingInEn.length) {
  console.error(`Locale parity mismatch for "${PREFIX}*" keys:`);
  if (missingInZh.length) {
    console.error(`  Missing in zh (present in en): ${JSON.stringify(missingInZh)}`);
  }
  if (missingInEn.length) {
    console.error(`  Missing in en (present in zh): ${JSON.stringify(missingInEn)}`);
  }
  process.exit(1);
}

console.log(`Locale parity OK: ${enKeys.size} ${PREFIX}* keys in both en and zh.`);
