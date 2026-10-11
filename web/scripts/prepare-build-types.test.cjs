const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { prepareBuildTypes } = require('./prepare-build-types.cjs');

for (const active of ['.next', '.next-review']) {
  test(`only ${active} supplies generated validators and the source config stays intact`, () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dbgpt-build-types-'));
    const original = JSON.stringify({
      compilerOptions: { strict: true, noEmit: true },
      include: [
        '**/*.ts',
        '**/*.tsx',
        'next-env.d.ts',
        '.next/types/**/*.ts',
        '.next-review/types/**/*.ts',
        'custom/types/**/*.ts',
      ],
      exclude: ['node_modules'],
    });
    fs.writeFileSync(path.join(root, 'tsconfig.json'), original);
    fs.mkdirSync(path.join(root, '.next'));
    fs.mkdirSync(path.join(root, '.next-review'));
    const generated = prepareBuildTypes(root, active);
    try {
      const config = JSON.parse(fs.readFileSync(path.join(root, generated.name), 'utf8'));
      const inactive = active === '.next' ? '.next-review' : '.next';
      assert.deepEqual(config.compilerOptions, { strict: true, noEmit: true });
      assert.ok(config.include.includes(`${active}/types/**/*.ts`));
      assert.ok(!config.include.includes(`${inactive}/types/**/*.ts`));
      assert.ok(config.include.includes('custom/types/**/*.ts'));
      assert.ok(config.exclude.includes(inactive));
      assert.ok(!config.exclude.includes(active));
      assert.equal(fs.readFileSync(path.join(root, 'tsconfig.json'), 'utf8'), original);
    } finally {
      generated.cleanup();
      assert.ok(!fs.existsSync(path.join(root, generated.name)));
      fs.unlinkSync(path.join(root, 'tsconfig.json'));
      fs.rmdirSync(path.join(root, '.next'));
      fs.rmdirSync(path.join(root, '.next-review'));
      fs.rmdirSync(root);
    }
  });
}
