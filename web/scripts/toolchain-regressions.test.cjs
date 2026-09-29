const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs');
const Module = require('node:module');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { test } = require('node:test');
const ts = require('typescript');

function loadTs(relative) {
  const filename = path.resolve(__dirname, '..', relative);
  const loaded = new Module(filename, module);
  loaded.paths = Module._nodeModulePaths(path.dirname(filename));
  loaded._compile(
    ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    }).outputText,
    filename,
  );
  return loaded.exports;
}

const { readDownloadError } = loadTs('lib/download-error.ts');
const { ee, EVENTS } = loadTs('utils/event-emitter.ts');

test('download errors are detected without a media type or with an incorrect one', async () => {
  for (const type of ['', 'application/json', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']) {
    const data = new Blob(['  {"err_msg":"dataset unavailable","success":false}'], { type });
    assert.equal(await readDownloadError(data), 'dataset unavailable');
  }
});

test('binary downloads are not decoded in full', async () => {
  const data = new Blob([new Uint8Array([0x50, 0x4b, 0x03, 0x04]), new Uint8Array(1024 * 1024)]);
  data.text = () => {
    throw new Error('Successful binary files must not be decoded in full.');
  };
  assert.equal(await readDownloadError(data), undefined);
});

test('only API error envelopes become error messages', async () => {
  assert.equal(await readDownloadError({ err_msg: 'access denied' }), 'access denied');
  for (const value of ['{invalid', '{"rows":[1,2]}', 'null', '[]', { err_msg: 12 }]) {
    assert.equal(await readDownloadError(value), undefined);
  }
});

test('unsubscribed task views stop receiving events without affecting other views', t => {
  const stale = [];
  const active = [];
  const stopStale = ee.on(EVENTS.TASK_CLICK, value => stale.push(value.taskId));
  const stopActive = ee.on(EVENTS.TASK_CLICK, value => active.push(value.taskId));
  t.after(() => {
    stopStale();
    stopActive();
  });
  ee.emit(EVENTS.TASK_CLICK, { taskId: 'before' });
  stopStale();
  ee.emit(EVENTS.TASK_CLICK, { taskId: 'after' });
  assert.deepEqual(stale, ['before']);
  assert.deepEqual(active, ['before', 'after']);
});

test('repeated cleanup leaves a later subscription intact', t => {
  const stopOld = ee.on(EVENTS.TASK_CLICK, () => {});
  stopOld();
  const received = [];
  const stopNew = ee.on(EVENTS.TASK_CLICK, value => received.push(value.taskId));
  t.after(stopNew);
  stopOld();
  ee.emit(EVENTS.TASK_CLICK, { taskId: 'new' });
  assert.deepEqual(received, ['new']);
});

function runnerFixture(t, childSource) {
  const temporaryRoot = fs.realpathSync(os.tmpdir());
  const root = fs.mkdtempSync(path.join(temporaryRoot, 'dbgpt-runner-tests-'));
  const scripts = path.join(root, 'scripts');
  const nextBin = path.join(root, 'node_modules', 'next', 'dist', 'bin');
  fs.mkdirSync(scripts, { recursive: true });
  fs.mkdirSync(nextBin, { recursive: true });
  fs.copyFileSync(path.join(__dirname, 'run-next.cjs'), path.join(scripts, 'run-next.cjs'));
  fs.writeFileSync(path.join(nextBin, 'next'), childSource);
  const runner = spawn(process.execPath, [path.join(scripts, 'run-next.cjs'), 'start'], {
    env: { ...process.env, NODE_OPTIONS: '' },
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
