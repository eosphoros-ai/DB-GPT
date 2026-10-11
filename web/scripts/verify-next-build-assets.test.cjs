const assert = require('node:assert/strict');
const { mkdirSync, mkdtempSync, rmSync, writeFileSync } = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { verifyNextBuildAssets } = require('./verify-next-build-assets.cjs');

/** Create a minimal temporary Next output tree with one HTML page and its referenced chunk. */
const makeBuild = () => {
  const root = mkdtempSync(path.join(os.tmpdir(), 'dbgpt-next-build-'));
  const pages = path.join(root, 'server', 'pages');
  const chunks = path.join(root, 'static', 'chunks');
  mkdirSync(pages, { recursive: true });
  mkdirSync(chunks, { recursive: true });
  writeFileSync(path.join(chunks, 'app.js'), 'console.log("ready")');
  writeFileSync(path.join(pages, 'index.html'), '<script src="/_next/static/chunks/app.js"></script>');
  return root;
};

test('accepts prerendered HTML whose local Next assets exist', t => {
  const root = makeBuild();
  t.after(() => rmSync(root, { recursive: true, force: true }));

  assert.deepEqual(verifyNextBuildAssets(root), {
    htmlFiles: 1,
    assetReferences: 1,
  });
});

test('rejects a successful-looking build with a missing chunk', t => {
  const root = makeBuild();
  t.after(() => rmSync(root, { recursive: true, force: true }));
  rmSync(path.join(root, 'static', 'chunks', 'app.js'));

  assert.throws(() => verifyNextBuildAssets(root), /index\.html -> static\/chunks\/app\.js/u);
});

test('decodes dynamic route chunk names before checking the file system', t => {
  const root = makeBuild();
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const chunks = path.join(root, 'static', 'chunks', 'pages', 'records');
  mkdirSync(chunks, { recursive: true });
  writeFileSync(path.join(chunks, '[id]-route.js'), 'console.log("dynamic")');
  writeFileSync(
    path.join(root, 'server', 'pages', 'dynamic.html'),
    '<script src="/_next/static/chunks/pages/records/%5Bid%5D-route.js"></script>',
  );

  assert.deepEqual(verifyNextBuildAssets(root), {
    htmlFiles: 2,
    assetReferences: 2,
  });
});

test('checks the copied static distribution, not only the intermediate build', t => {
  const root = mkdtempSync(path.join(os.tmpdir(), 'dbgpt-export-'));
  t.after(() => rmSync(root, { recursive: true, force: true }));
  const asset = path.join(root, '_next', 'static', 'app.js');
  mkdirSync(path.dirname(asset), { recursive: true });
  writeFileSync(asset, 'console.log("exported")');
  writeFileSync(path.join(root, 'index.html'), '<script src="/_next/static/app.js"></script>');
  assert.deepEqual(verifyNextBuildAssets(root, { staticExport: true }), { htmlFiles: 1, assetReferences: 1 });
  rmSync(asset);
  assert.throws(() => verifyNextBuildAssets(root, { staticExport: true }), /missing local asset/);
});
