const assert = require('node:assert/strict');
const { spawn, spawnSync } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { test } = require('node:test');

function runnerFixture(t, childSource, nodeOptions = '', script = 'run-next.cjs') {
  const temporaryRoot = fs.realpathSync(os.tmpdir());
  const root = fs.mkdtempSync(path.join(temporaryRoot, 'dbgpt-runner-tests-'));
  const scripts = path.join(root, 'scripts');
  const nextBin = path.join(root, 'node_modules', 'next', 'dist', 'bin');
  fs.mkdirSync(scripts, { recursive: true });
  fs.mkdirSync(nextBin, { recursive: true });
  fs.copyFileSync(path.join(__dirname, script), path.join(scripts, script));
  if (script === 'build-web.cjs') {
    fs.writeFileSync(
      path.join(scripts, 'prepare-build-types.cjs'),
      'exports.prepareBuildTypes = () => ({ name: "fixture.json", cleanup() {} });',
    );
    fs.writeFileSync(
      path.join(scripts, 'verify-next-build-assets.cjs'),
      'exports.verifyNextBuildAssets = () => ({ htmlFiles: 0, assetReferences: 0 });',
    );
    fs.writeFileSync(path.join(scripts, 'graceful-fs-register.cjs'), '');
  }
  fs.writeFileSync(path.join(nextBin, 'next'), childSource);
  const runner = spawn(process.execPath, [path.join(scripts, script), 'start'], {
    env: { ...process.env, NODE_OPTIONS: nodeOptions },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  let childPid;
  t.after(() => {
    if (runner.exitCode === null && runner.signalCode === null) runner.kill('SIGKILL');
    if (childPid) {
      try {
        process.kill(childPid, 'SIGKILL');
      } catch (error) {
        if (error.code !== 'ESRCH') throw error;
      }
    }
    // Only delete the unique fixture directly beneath the known temporary root.
    assert.equal(path.dirname(path.resolve(root)), temporaryRoot);
    assert.ok(path.basename(root).startsWith('dbgpt-runner-tests-'));
    fs.rmSync(root, { recursive: true, force: true });
  });
  return {
    runner,
    setChildPid: value => {
      childPid = value;
    },
  };
}

for (const script of ['run-next.cjs', 'build-web.cjs']) {
  for (const [options, expectedMiB] of [
    ['', 8192],
    ['--trace-warnings', 8192],
    ['--trace-warnings --max-old-space-size=12288', 12288],
    ['--max_old_space_size=2048', 2048],
    ['--max-old-space-size="2048"', 2048],
    ['"--max-old-space-size=3072"', 3072],
    ['--max-old-space-size=3072 --max_old_space_size=4096', 4096],
    ['--title=foo--max-old-space-size=4096', 8192],
    ['--title="foo --max-old-space-size=4096"', 8192],
    ['--title="--max-old-space-size=4096"', 8192],
  ]) {
    test(`${script} preserves Node option semantics: ${options || '(default)'}`, { timeout: 10000 }, async t => {
      const { runner } = runnerFixture(
        t,
        `console.log(JSON.stringify({
        heap: require('node:v8').getHeapStatistics().heap_size_limit,
        options: process.env.NODE_OPTIONS
      }));`,
        options,
        script,
      );
      let output = '';
      let errors = '';
      runner.stdout.on('data', chunk => {
        output += chunk;
      });
      runner.stderr.on('data', chunk => {
        errors += chunk;
      });
      const [code] = await once(runner, 'close');
      assert.equal(code, 0, errors);
      const child = JSON.parse(output.split('\n')[0]);
      const control = spawnSync(
        process.execPath,
        [`--max-old-space-size=${expectedMiB}`, '-p', "require('node:v8').getHeapStatistics().heap_size_limit"],
        { env: { ...process.env, NODE_OPTIONS: '' }, encoding: 'utf8' },
      );
      assert.equal(control.status, 0, control.stderr);
      assert.equal(child.heap, Number(control.stdout.trim()));
      assert.ok(child.options.includes(options));
    });
  }
}

test('the Next wrapper preserves the child exit status', { timeout: 10000 }, async t => {
  const { runner } = runnerFixture(t, 'process.exit(23);');
  const [code, signal] = await once(runner, 'exit');
  assert.equal(code, 23);
  assert.equal(signal, null);
});

for (const graceful of [true, false]) {
  test(
    `direct wrapper signals ${graceful ? 'allow graceful child shutdown' : 'preserve an unhandled child signal'}`,
    {
      timeout: 10000,
      skip: process.platform === 'win32' ? 'POSIX signal delivery is checked on the Ubuntu/macOS matrix.' : false,
    },
    async t => {
      const { runner, setChildPid } = runnerFixture(
        t,
        `
      const net = require('node:net');
      const server = net.createServer();
      ${graceful ? "process.on('SIGTERM', () => server.close(() => process.exit(0)));" : ''}
      server.listen(0, '127.0.0.1', () => console.log(JSON.stringify({ pid: process.pid, port: server.address().port })));
    `,
      );
      const ready = await new Promise((resolve, reject) => {
        let output = '';
        runner.on('error', reject);
        runner.stdout.on('data', chunk => {
          output += chunk;
          if (output.includes('\n')) resolve(JSON.parse(output.split('\n')[0]));
        });
      });
      setChildPid(ready.pid);
      const exited = once(runner, 'exit');
      runner.kill(graceful ? 'SIGTERM' : 'SIGINT');
      const [code, signal] = await exited;
      assert.equal(code, graceful ? 0 : null);
      assert.equal(signal, graceful ? null : 'SIGINT');
      const probe = net.createServer();
      try {
        await new Promise((resolve, reject) => {
          probe.once('error', reject);
          probe.listen(ready.port, '127.0.0.1', resolve);
        });
      } finally {
        await new Promise(resolve => probe.close(resolve));
      }
    },
  );
}
