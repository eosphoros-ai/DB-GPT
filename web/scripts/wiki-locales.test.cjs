const assert = require('node:assert/strict');
const path = require('node:path');
const { test } = require('node:test');
const ts = require('typescript');

// Compile a consumer of the real resources so a broad record annotation or a
// circular Resources dependency cannot silently weaken application types.
test('Wiki and source translations retain finite keys and string return types', () => {
  const root = path.resolve(__dirname, '..');
  const filename = path.join(root, 'wiki-locales-type-fixture.ts');
  const source = `
    import i18n, { I18nKeys } from './app/i18n';
    import en from './locales/en';
    import zh from './locales/zh';
    type Assert<T extends true> = T;
    type FiniteKeys = Assert<string extends I18nKeys ? false : true>;
    type HasWiki = Assert<'wiki_tab_label' extends I18nKeys ? true : false>;
    type HasSources = Assert<'ks_tab_label' extends I18nKeys ? true : false>;
    const wiki: string = i18n.t('wiki_tab_label');
    const sources: string = i18n.t('ks_tab_label');
    const existing: string = i18n.t('Knowledge_Space');
    const enWiki: string = en.wiki_tab_label;
    const zhWiki: string = zh.wiki_tab_label;
    const enSource: string = en.ks_tab_label;
    const zhSource: string = zh.ks_tab_label;
    // @ts-expect-error unknown translation keys must still be rejected
    i18n.t('__missing_wiki_merge_translation__');
  `;
  const config = ts.readConfigFile(path.join(root, 'tsconfig.json'), ts.sys.readFile);
  assert.equal(config.error, undefined);
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, root);
  const options = { ...parsed.options, incremental: false, noEmit: true };
  delete options.tsBuildInfoFile;
  const host = ts.createCompilerHost(options);
  const originalGetSourceFile = host.getSourceFile;
  host.getSourceFile = (file, languageVersion, onError, shouldCreateNewSourceFile) =>
    file === filename
      ? ts.createSourceFile(filename, source, languageVersion, true)
      : originalGetSourceFile(file, languageVersion, onError, shouldCreateNewSourceFile);
  const program = ts.createProgram([filename], options, host);
  const diagnostics = ts.getPreEmitDiagnostics(program);
  assert.equal(
    diagnostics.length,
    0,
    ts.formatDiagnosticsWithColorAndContext(diagnostics, {
      getCanonicalFileName: file => file,
      getCurrentDirectory: () => root,
      getNewLine: () => '\n',
    }),
  );
});
