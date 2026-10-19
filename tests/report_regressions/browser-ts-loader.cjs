const ts = require('../../web/node_modules/typescript');
module.exports = function (source) {
  if (process.env.DBGPT_BROWSER_BASELINE === '1' && this.resourcePath.endsWith('ReportIframe.tsx')) {
    source = require('child_process').execFileSync('git', ['show', '55bc7e43e6a9db30815078ef824e4e4177068623:web/new-components/report/ReportIframe.tsx'], { cwd: this.rootContext, encoding: 'utf8' });
  }
  return ts.transpileModule(source, { fileName: this.resourcePath, compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.ESNext,
    target: ts.ScriptTarget.ES2020, esModuleInterop: true,
  }}).outputText;
};
