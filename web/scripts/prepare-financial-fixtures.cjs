const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const repo = path.resolve(__dirname, '../..');
const backend = path.resolve(process.env.FINANCIAL_FIXTURE_BACKEND_ROOT || repo);
const generator = path.join(backend, 'scripts/verify_financial_comparison.py');
const output = path.join(repo, 'web/node_modules/.cache/financial-comparison');
const runtime = path.join(output, 'runtime.html');

if (!fs.existsSync(generator)) {
  throw new Error(
    'Financial fixtures require the companion backend. Merge PR #3310 first, or set ' +
      'FINANCIAL_FIXTURE_BACKEND_ROOT to its prepared checkout.',
  );
}

function run(command, args, cwd, env = process.env) {
  const result = spawnSync(command, args, { cwd, env, stdio: 'inherit', windowsHide: true });
  if (result.error) throw result.error;
  if (result.status !== 0) process.exit(result.status || 1);
}

run(process.execPath, [path.join(repo, 'standalone/financial-analysis/build.cjs'), runtime], repo);
const sources = fs.readdirSync(path.join(backend, 'packages'))
  .map(name => path.join(backend, 'packages', name, 'src'))
  .filter(source => fs.existsSync(source));
run('uv', ['run', '--no-sync', 'python', generator, '--output-dir', output, '--runtime', runtime], backend, {
  ...process.env,
  PYTHONPATH: [...sources, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter),
  PYTHONIOENCODING: 'utf-8',
});
