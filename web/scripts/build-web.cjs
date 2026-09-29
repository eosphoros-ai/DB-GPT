const { spawnSync } = require('node:child_process');
const path = require('node:path');
const { verifyNextBuildAssets } = require('./verify-next-build-assets.cjs');
const { prepareBuildTypes } = require('./prepare-build-types.cjs');

if (process.argv.includes('--export')) process.env.DBGPT_WEB_STATIC_EXPORT = '1';
if (process.argv.includes('--production-env')) process.env.APP_ENV = 'prod';

const nextBin = path.join(__dirname, '..', 'node_modules', 'next', 'dist', 'bin', 'next');
const gracefulFsRegister = path.join(__dirname, 'graceful-fs-register.cjs');

const run = (args, typeConfig) => {
  const result = spawnSync(process.execPath, [nextBin, 'build', '--webpack', ...args], {
    cwd: path.join(__dirname, '..'),
    env: {
      ...process.env,
      DBGPT_BUILD_TSCONFIG: typeConfig,
      NODE_OPTIONS: [
        process.env.NODE_OPTIONS,
        '--max_old_space_size=8192',
        ['win32', 'darwin'].includes(process.platform) ? `--require=${gracefulFsRegister}` : null,
      ]
        .filter(Boolean)
        .join(' '),
    },
    stdio: 'inherit',
  });
  if (result.error) throw result.error;
  return result.status ?? 1;
};

// Keep compilation and static generation in one process so HTML and chunk
// references come from the same build. Windows and macOS use a file-system limiter.
const typeConfig = prepareBuildTypes(path.join(__dirname, '..'), process.env.NEXT_DIST_DIR || '.next');
let status;
try {
  status = run([], typeConfig.name);
} finally {
  typeConfig.cleanup();
}
if (status !== 0) process.exit(status);

const verification = verifyNextBuildAssets(path.join(__dirname, '..', process.env.NEXT_DIST_DIR || '.next'));
console.log(
  `[web build] Verified ${verification.htmlFiles} HTML files and ${verification.assetReferences} local assets.`,
);
if (process.env.DBGPT_WEB_STATIC_EXPORT === '1') {
  const exported = verifyNextBuildAssets(path.join(__dirname, '..', 'out'), { staticExport: true });
  console.log(
    `[web export] Verified ${exported.htmlFiles} exported HTML files and ${exported.assetReferences} local assets.`,
  );
}
