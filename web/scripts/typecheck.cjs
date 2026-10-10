const { spawnSync } = require('node:child_process');
const path = require('node:path');
const { prepareBuildTypes } = require('./prepare-build-types.cjs');

const webRoot = path.join(__dirname, '..');
const config = prepareBuildTypes(webRoot, process.env.NEXT_DIST_DIR || '.next');
let status;
try {
  const result = spawnSync(
    process.execPath,
    [path.join(webRoot, 'node_modules/typescript/bin/tsc'), '--project', config.name, '--noEmit'],
    { cwd: webRoot, stdio: 'inherit' },
  );
  if (result.error) throw result.error;
  status = result.status ?? 1;
} finally {
  config.cleanup();
}
process.exitCode = status;
