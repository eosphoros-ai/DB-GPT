/**
 * Workaround for a Next 16 react-refresh loader bug.
 *
 * Next's compiled refresh loader (next/dist/compiled/@next/react-refresh-
 * utils/dist/loader.js) appends a refresh-runtime snippet to every module it
 * processes, but only picks the CommonJS variant when the file ends in
 * `.cjs`. Any CommonJS `.js` module that becomes a refresh boundary (e.g.
 * `@babel/runtime` helpers pulled in by antd) therefore receives the
 * ESM-only `import.meta.webpackHot.accept()` snippet and fails webpack
 * parsing with:
 *
 *   Module parse failed: Cannot use 'import.meta' outside a module
 *
 * This shim mirrors Next's loader exactly, but chooses the runtime variant
 * by inspecting the source (CommonJS vs ESM) instead of the file extension.
 * Wired in from next.config.js (dev client builds only).
 */
let cached = null;

function runtimes() {
  if (cached) return cached;
  // Mirror Next's loader: take the *exported function's source* (not the
  // file text) and slice its body between the outermost braces.
  const runtimeModule = require('next/dist/compiled/@next/react-refresh-utils/dist/internal/ReactRefreshModule.runtime.js');
  let src = (runtimeModule.default || runtimeModule).toString();
  src = src
    .slice(src.indexOf('{') + 1, src.lastIndexOf('}'))
    .replace('global.importMeta', 'import.meta');
  cached = {
    esm: src,
    cjs: src.replace('import.meta.webpackHot', 'module.hot'),
  };
  return cached;
}

function looksCommonJs(source) {
  if (/^\s*(import|export)[\s{]/m.test(source)) return false;
  return /module\.exports|exports\.[A-Za-z_$]|Object\.defineProperty\(\s*exports/.test(source);
}

module.exports = function reactRefreshLoaderCjsSafe(source, inputSourceMap) {
  const { esm, cjs } = runtimes();
  const useCjs = this.resourcePath.endsWith('.cjs') || looksCommonJs(source);
  this.callback(null, `${source}\n\n;${useCjs ? cjs : esm}`, inputSourceMap);
};
