const assert = require('node:assert/strict');
const { randomBytes } = require('node:crypto');
const { readFileSync } = require('node:fs');
const Module = require('node:module');
const path = require('node:path');
const { test } = require('node:test');
const ts = require('typescript');

// Load the actual wrapper without adding a browser runner or opening a socket.
process.env.SECRET_COOKIE_PASSWORD = randomBytes(32).toString('hex');
const filename = path.join(__dirname, 'session.ts');
const compiled = ts.transpileModule(readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, esModuleInterop: true },
}).outputText;
const loaded = new Module(filename, module);
loaded.paths = Module._nodeModulePaths(__dirname);
loaded._compile(compiled, filename);
const { withSessionRoute, withSessionSsr } = loaded.exports;

/** Create an in-memory response header store for exercising real iron-session cookies without a server. */
function response() {
  const headers = new Map();
  return {
    headersSent: false,
    getHeader: name => headers.get(name.toLowerCase()),
    setHeader: (name, value) => headers.set(name.toLowerCase(), value),
  };
}

test('API wrapper saves and recovers the session before calling the handler', async () => {
  const outgoing = response();
  const write = withSessionRoute(async req => {
    assert(req.session);
    req.session.user = { id: 17, email: 'session-test@example.invalid' };
    await req.session.save();
    return 'saved';
  });
  assert.equal(await write({ headers: {} }, outgoing), 'saved');
  const cookies = outgoing.getHeader('set-cookie');
  const cookie = (Array.isArray(cookies) ? cookies[0] : cookies).split(';')[0];
  assert(cookie.startsWith('dbgpt-portal='));
  assert(!cookie.includes('session-test@example.invalid'));
  const read = withSessionRoute(async req => req.session.user);
  assert.deepEqual(await read({ headers: { cookie } }, response()), { id: 17, email: 'session-test@example.invalid' });
});

test('SSR wrapper awaits the handler and preserves its redirect result', async () => {
  const context = { req: { headers: {} }, res: response() };
  const wrapped = withSessionSsr(async received => {
    assert.equal(received, context);
    assert(received.req.session);
    assert.equal(received.req.session.user, undefined);
    return { redirect: { destination: '/login', permanent: false } };
  });
  assert.deepEqual(await wrapped(context), { redirect: { destination: '/login', permanent: false } });
});
