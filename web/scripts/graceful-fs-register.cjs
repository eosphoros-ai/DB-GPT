// Queue transient EMFILE failures while Next.js traces and prerenders the app.
require('graceful-fs').gracefulify(require('node:fs'));

// Next's output tracer defaults to a level of file-system concurrency that can
// exceed the OS per-process handle limit in this repository. Keep the
// tracer deterministic without disabling output tracing or hiding build errors.
const nft = require('next/dist/compiled/@vercel/nft');
const nodeFileTrace = nft.nodeFileTrace;
Object.defineProperty(nft, 'nodeFileTrace', {
  configurable: true,
  enumerable: true,
  value: (files, options = {}) =>
    nodeFileTrace(files, {
      ...options,
      fileIOConcurrency: Math.min(options.fileIOConcurrency ?? 64, 64),
    }),
});

// Some Next.js build-trace work happens outside @vercel/nft. Limit the
// short-lived promise operations too so those phases cannot immediately refill
// the handle table after the tracer completes.
const fsPromises = require('node:fs/promises');
const maxConcurrentOperations = 64;
let activeOperations = 0;
const waitingOperations = [];

const acquire = () =>
  new Promise(resolve => {
    if (activeOperations < maxConcurrentOperations) {
      activeOperations += 1;
      resolve();
      return;
    }
    waitingOperations.push(resolve);
  });

const release = () => {
  const next = waitingOperations.shift();
  if (next) {
    next();
    return;
  }
  activeOperations -= 1;
};

for (const method of ['readFile', 'writeFile', 'stat', 'lstat', 'readlink', 'readdir']) {
  const original = fsPromises[method].bind(fsPromises);
  fsPromises[method] = async (...args) => {
    await acquire();
    try {
      return await original(...args);
    } finally {
      release();
    }
  };
}
