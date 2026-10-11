const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { prepareBuildTypes } = require('./prepare-build-types.cjs');

test('dev followed by build keeps one validator and still rejects application type errors', () => {
  const ts = require('typescript');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dbgpt-build-types-sequence-'));
  const directories = ['.next', '.next/types', '.next/dev', '.next/dev/types'];
  const files = ['tsconfig.json', 'app.ts', '.next/types/validator.ts', '.next/dev/types/validator.ts'];
  for (const directory of directories) fs.mkdirSync(path.join(root, directory));
  fs.writeFileSync(
    path.join(root, 'tsconfig.json'),
    JSON.stringify({
      compilerOptions: { strict: true, noEmit: true, skipLibCheck: true, types: [] },
      include: ['**/*.ts', '.next/types/**/*.ts', '.next/dev/types/**/*.ts'],
    }),
  );
  for (const directory of ['.next/types', '.next/dev/types']) {
    fs.writeFileSync(path.join(root, directory, 'validator.ts'), 'type PagesPageConfig = { name: string };');
  }
  fs.writeFileSync(path.join(root, 'app.ts'), 'const invalid: number = "must still fail";');
  const generated = prepareBuildTypes(root);
  try {
    const config = ts.readConfigFile(path.join(root, generated.name), ts.sys.readFile);
    const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, root);
    const diagnostics = ts.getPreEmitDiagnostics(ts.createProgram(parsed.fileNames, parsed.options));
    assert.ok(
      diagnostics.some(diagnostic => diagnostic.code === 2322),
      'application types must remain checked',
    );
    assert.ok(
      !diagnostics.some(diagnostic => diagnostic.code === 2300),
      'duplicate generated validators must be excluded',
    );
    assert.ok(parsed.fileNames.some(file => file.endsWith('/.next/types/validator.ts')));
    assert.ok(!parsed.fileNames.some(file => file.endsWith('/.next/dev/types/validator.ts')));
  } finally {
    generated.cleanup();
    for (const file of files) fs.unlinkSync(path.join(root, file));
    for (const directory of directories.reverse()) fs.rmdirSync(path.join(root, directory));
    fs.rmdirSync(root);
  }
});

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
