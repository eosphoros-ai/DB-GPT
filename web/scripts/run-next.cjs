const { spawn } = require('node:child_process');
const path = require('node:path');

const nextBin = path.join(__dirname, '..', 'node_modules', 'next', 'dist', 'bin', 'next');
const args = process.argv.slice(2);

if (args.length === 0) {
  console.error('Usage: node scripts/run-next.cjs <dev|start> [...arguments]');
  process.exit(1);
}

// Node uses the last value of a singleton option. Put the default first so Node
// itself preserves explicit limits and handles quoting/option values correctly.
const nodeOptions = ['--max_old_space_size=8192', process.env.NODE_OPTIONS].filter(Boolean).join(' ');

const child = spawn(process.execPath, [nextBin, ...args], {
  cwd: path.join(__dirname, '..'),
  env: { ...process.env, NODE_OPTIONS: nodeOptions },
  stdio: 'inherit',
});

// Supervisors may signal only this wrapper PID rather than its process group.
// Keep the wrapper alive until Next finishes shutting down.
const signalHandlers = new Map();
for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  /** Relay the supervisor's signal to Next while the child is still running. */
  const forward = () => {
    if (child.exitCode === null && child.signalCode === null) child.kill(signal);
  };
  signalHandlers.set(signal, forward);
  process.on(signal, forward);
}
/** Detach forwarding handlers before propagating child completion or a spawn error. */
const removeSignalHandlers = () => {
  for (const [signal, handler] of signalHandlers) process.removeListener(signal, handler);
};

child.on('error', error => {
  removeSignalHandlers();
  console.error(error);
  process.exitCode = 1;
});

child.on('exit', (code, signal) => {
  // Restore the default handlers before reproducing the child's exit signal.
  removeSignalHandlers();
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exitCode = code ?? 1;
});
