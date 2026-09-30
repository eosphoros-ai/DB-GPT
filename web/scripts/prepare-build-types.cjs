const fs = require('node:fs');
const path = require('node:path');

// Next adds generated type paths to tsconfig. Isolated builds must not load
// both the old and current validator modules, which declare identical names.
/** Write an exclusive temporary tsconfig containing only the active Next type outputs; the caller must invoke cleanup. */
function prepareBuildTypes(webRoot, distDir = '.next') {
  const source = fs.readFileSync(path.join(webRoot, 'tsconfig.json'), 'utf8').replace(/^\uFEFF/, '');
  const config = JSON.parse(source);
  const active = distDir.replaceAll('\\', '/').replace(/\/$/, '');
  const previous = (config.include || [])
    .map(value => /^(.+?)\/(?:dev\/)?types\/\*\*\/\*\.ts$/.exec(value))
    .filter(match => match && match[1].startsWith('.next'))
    .map(match => match[1]);
  const inactive = new Set([
    ...previous,
    ...fs
      .readdirSync(webRoot, { withFileTypes: true })
      .filter(entry => entry.isDirectory() && entry.name.startsWith('.next'))
      .map(entry => entry.name),
  ]);
  inactive.delete(active);
  const generatedPath = /^\.next[^/]*\/(?:dev\/)?types\/\*\*\/\*\.ts$/;
  config.include = [
    ...(config.include || []).filter(value => !generatedPath.test(value)),
    `${active}/types/**/*.ts`,
    `${active}/dev/types/**/*.ts`,
  ];
  config.exclude = [...new Set([...(config.exclude || []).filter(value => value !== active), ...inactive])];
  const name = `.tsconfig-build-${process.pid}.json`;
  const target = path.join(webRoot, name);
  fs.writeFileSync(target, JSON.stringify(config, null, 2) + '\n', { flag: 'wx' });
  return {
    name,
    /** Remove the temporary type configuration created by this invocation. */
    cleanup: () => fs.unlinkSync(target),
  };
}

module.exports = { prepareBuildTypes };
