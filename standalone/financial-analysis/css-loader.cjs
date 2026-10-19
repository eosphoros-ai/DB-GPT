const path = require('node:path');
const postcss = require('../../web/node_modules/postcss');
const local = require('../../web/node_modules/next/dist/compiled/postcss-modules-local-by-default');
const scope = require('../../web/node_modules/next/dist/compiled/postcss-modules-scope');
module.exports = function (source) {
  const done = this.async();
  const name = path.basename(this.resourcePath).replace(/\W/g, '_');
  postcss([
    local(),
    scope({ generateScopedName: value => `report_${name}_${value}` }),
  ]).process(source, { from: this.resourcePath }).then(result => {
    const names = {};
    result.root.walkRules(':export', rule => {
      rule.walkDecls(decl => { names[decl.prop] = decl.value; });
      rule.remove();
    });
    this.emitFile(`${name}.css`, result.root.toString());
    done(null, `export default ${JSON.stringify(names)};`);
  }, done);
};
