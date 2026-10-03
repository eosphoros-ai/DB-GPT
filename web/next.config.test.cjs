const assert = require('node:assert/strict');
const test = require('node:test');
const { PHASE_DEVELOPMENT_SERVER, PHASE_PRODUCTION_BUILD } = require('next/constants');
const config = require('./next.config.js');

test('production enables strict type checks and retains the official API target', async () => {
  const production = config(PHASE_PRODUCTION_BUILD);
  assert.equal(production.typescript.ignoreBuildErrors, false);
  assert.equal(production.env.API_BASE_URL, 'http://127.0.0.1:5670');
  assert.deepEqual(await production.rewrites(), [
    {
      source: '/api/v1/:path*',
      destination: 'http://127.0.0.1:5670/api/v1/:path*',
    },
  ]);
  assert.equal(production.experimental?.cpus, process.platform === 'win32' ? 1 : undefined);
  assert.equal(config(PHASE_DEVELOPMENT_SERVER).experimental?.cpus, undefined);
});

test('static bundle uses Next export mode while server builds retain API routes', () => {
  const previous = process.env.DBGPT_WEB_STATIC_EXPORT;
  try {
    process.env.DBGPT_WEB_STATIC_EXPORT = '1';
    const exported = config(PHASE_PRODUCTION_BUILD);
    assert.equal(exported.output, 'export');
    assert.equal(exported.rewrites, undefined);
  } finally {
    if (previous === undefined) delete process.env.DBGPT_WEB_STATIC_EXPORT;
    else process.env.DBGPT_WEB_STATIC_EXPORT = previous;
  }
  assert.equal(config(PHASE_PRODUCTION_BUILD).output, undefined);
});
