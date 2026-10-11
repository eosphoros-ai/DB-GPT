const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { test } = require('node:test');

test('build children preload the file limiter on every OS, including paths with spaces', t => {
  const temporaryRoot = fs.realpathSync(os.tmpdir());
  const root = fs.mkdtempSync(path.join(temporaryRoot, 'dbgpt build launcher '));
  t.after(() => {
    assert.equal(path.dirname(path.resolve(root)), temporaryRoot);
    assert.ok(path.basename(root).startsWith('dbgpt build launcher '));
    fs.rmSync(root, { recursive: true, force: true });
  });
  const scripts = path.join(root, 'scripts');
  const nextBin = path.join(root, 'node_modules/next/dist/bin');
  fs.mkdirSync(scripts, { recursive: true });
  fs.mkdirSync(nextBin, { recursive: true });
  fs.copyFileSync(path.join(__dirname, 'build-web.cjs'), path.join(scripts, 'build-web.cjs'));
  fs.writeFileSync(path.join(scripts, 'graceful-fs-register.cjs'), 'process.env.TEST_LIMITER_LOADED = "yes";');
  fs.writeFileSync(
    path.join(scripts, 'prepare-build-types.cjs'),
    'exports.prepareBuildTypes = () => ({ name: "types.json", cleanup() {} });',
  );
  fs.writeFileSync(
    path.join(scripts, 'verify-next-build-assets.cjs'),
    'exports.verifyNextBuildAssets = () => ({ htmlFiles: 1, assetReferences: 1 });',
  );
  fs.writeFileSync(
    path.join(nextBin, 'next'),
    `
    require('node:assert/strict').equal(process.env.TEST_LIMITER_LOADED, 'yes');
    require('node:assert/strict').equal(process.env.DBGPT_BUILD_TSCONFIG, 'types.json');
    console.log('preload verified');
  `,
  );
  const result = spawnSync(process.execPath, [path.join(scripts, 'build-web.cjs'), '--export'], {
    encoding: 'utf8',
    env: { ...process.env, NODE_OPTIONS: '', TEST_LIMITER_LOADED: '' },
  });
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout, /preload verified/);
  assert.match(result.stdout, /\[web export\] Verified/);
});
