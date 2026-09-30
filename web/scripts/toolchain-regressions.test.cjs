const assert = require('node:assert/strict');
const { spawn, spawnSync } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs');
const Module = require('node:module');
const net = require('node:net');
const os = require('node:os');
const path = require('node:path');
const { test } = require('node:test');
const ts = require('typescript');

/** Load a real TypeScript module as CommonJS for the Node regression tests without a browser bundler. */
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
const { DocumentFormattingEditProvider, DocumentRangeFormattingEditProvider } = loadTs(
  'components/chat/ob-editor/format.ts',
);

test('SQL formatting preserves quoted delimiters and formats only the requested range', () => {
  const plugin = { modelOptionsMap: new Map([['sql-model', { delimiter: ';' }]]) };
  const full = { startLineNumber: 1, startColumn: 1, endLineNumber: 1, endColumn: 80 };
  const selection = { startLineNumber: 1, startColumn: 1, endLineNumber: 1, endColumn: 32 };
  const source = "select 'a;b' as value from example;";
  const model = { id: 'sql-model', getFullModelRange: () => full, getValueInRange: () => source };
  const options = { insertSpaces: true, tabSize: 2 };
  const token = { isCancellationRequested: false };
  const documentEdits = new DocumentFormattingEditProvider(plugin, 'mysql').provideDocumentFormattingEdits(
    model,
    options,
    token,
  );
  assert.equal(documentEdits.length, 1);
  assert.equal(documentEdits[0].range, full);
  assert.match(documentEdits[0].text, /'a;b'/);
  assert.match(documentEdits[0].text, /\n/);
  const selectedEdits = new DocumentRangeFormattingEditProvider(plugin, 'mysql').provideDocumentRangeFormattingEdits(
    model,
    selection,
    options,
    token,
  );
  assert.equal(selectedEdits[0].range, selection);
  assert.equal(selectedEdits[0].text, documentEdits[0].text);
});

test('formatting leaves incomplete SQL, cancelled requests and custom delimiters intact', () => {
  const options = { insertSpaces: true, tabSize: 2 };
  const plugin = { modelOptionsMap: new Map() };
  const model = { id: 'sql-model', getFullModelRange: () => ({}), getValueInRange: () => "select 'unterminated" };
  const provider = new DocumentFormattingEditProvider(plugin, 'mysql');
  assert.deepEqual(provider.provideDocumentFormattingEdits(model, options, { isCancellationRequested: false }), []);
  model.getValueInRange = () => 'select 1';
  assert.deepEqual(provider.provideDocumentFormattingEdits(model, options, { isCancellationRequested: true }), []);
  plugin.modelOptionsMap.set('sql-model', { delimiter: '$$' });
  assert.deepEqual(provider.provideDocumentFormattingEdits(model, options, { isCancellationRequested: false }), []);
});

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

/** Spawn a copied launcher with a fake Next entrypoint and register cleanup for its process and temporary directory. */
function runnerFixture(t, childSource, nodeOptions = '') {
  const temporaryRoot = fs.realpathSync(os.tmpdir());
  const root = fs.mkdtempSync(path.join(temporaryRoot, 'dbgpt-runner-tests-'));
  const scripts = path.join(root, 'scripts');
  const nextBin = path.join(root, 'node_modules', 'next', 'dist', 'bin');
  fs.mkdirSync(scripts, { recursive: true });
  fs.mkdirSync(nextBin, { recursive: true });
  fs.copyFileSync(path.join(__dirname, 'run-next.cjs'), path.join(scripts, 'run-next.cjs'));
  fs.writeFileSync(path.join(nextBin, 'next'), childSource);
  const runner = spawn(process.execPath, [path.join(scripts, 'run-next.cjs'), 'start'], {
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

for (const [options, expectedMiB] of [
  ['', 8192],
  ['--trace-warnings', 8192],
  ['--trace-warnings --max-old-space-size=12288', 12288],
  ['--trace-warnings --max_old_space_size=2048', 2048],
  ['--trace-warnings --max-old-space-size="2048"', 2048],
  ['--trace-warnings "--max-old-space-size=3072"', 3072],
  ['--trace-warnings --max-old-space-size=3072 --max_old_space_size=4096', 4096],
  ['--trace-warnings --title=foo--max-old-space-size=4096', 8192],
  ['--trace-warnings --title="foo --max-old-space-size=4096"', 8192],
  ['--trace-warnings --title="--max-old-space-size=4096"', 8192],
  ['--trace-warnings --title="foo \\"--max-old-space-size=4096\\""', 8192],
]) {
  test(`the Next child applies the heap options: ${options || '(empty)'}`, { timeout: 10000 }, async t => {
    const { runner } = runnerFixture(
      t,
      `console.log(JSON.stringify({
        heapLimitMiB: require('node:v8').getHeapStatistics().heap_size_limit / 1024 / 1024,
        options: process.env.NODE_OPTIONS
      }));`,
      options,
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
    const child = JSON.parse(output);
    // Compare to this Node version directly: V8's young-generation allowance
    // changes between releases, independently of the requested old-space limit.
    const control = spawnSync(
      process.execPath,
      [
        `--max-old-space-size=${expectedMiB}`,
        '-p',
        "require('node:v8').getHeapStatistics().heap_size_limit / 1024 / 1024",
      ],
      { env: { ...process.env, NODE_OPTIONS: '' }, encoding: 'utf8' },
    );
    assert.equal(control.status, 0, control.stderr);
    assert.equal(child.heapLimitMiB, Number(control.stdout.trim()));
    assert.ok(child.options.includes(options), 'Preserve all configured NODE_OPTIONS.');
  });
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
