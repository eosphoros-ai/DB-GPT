const { spawn } = require('node:child_process');
const path = require('node:path');

const nextBin = path.join(__dirname, '..', 'node_modules', 'next', 'dist', 'bin', 'next');
const args = process.argv.slice(2);

if (args.length === 0) {
  console.error('Usage: node scripts/run-next.cjs <dev|start> [...arguments]');
  process.exit(1);
}

const withoutHeapLimit = (process.env.NODE_OPTIONS || '')
  .replace(/--max(?:-|_)old(?:-|_)space(?:-|_)size(?:=|\s+)\d+/giu, '')
  .trim();
const nodeOptions = [withoutHeapLimit, '--max_old_space_size=8192'].filter(Boolean).join(' ');

const child = spawn(process.execPath, [nextBin, ...args], {
  cwd: path.join(__dirname, '..'),
  env: { ...process.env, NODE_OPTIONS: nodeOptions },
  stdio: 'inherit',
});

child.on('error', error => {
  console.error(error);
  process.exitCode = 1;
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exitCode = code ?? 1;
});
