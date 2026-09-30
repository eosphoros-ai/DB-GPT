import type Plugin from '@oceanbase-odc/monaco-plugin-ob';
import type { CancellationToken, editor, IRange, languages } from 'monaco-editor';
import { format } from 'sql-formatter';

// Use the formatter already used by DB-GPT's SQL preview. The upstream OB
// formatting adapter imports ~129 MB of generated parsers into the page graph;
// completion still uses OB's unchanged, prebuilt SQL workers.
class SqlFormattingProvider {
  constructor(
    private plugin: Plugin,
    private dialect: string,
  ) {}

  protected edits(
    model: editor.ITextModel,
    range: IRange,
    options: languages.FormattingOptions,
    token: CancellationToken,
  ) {
    if (token.isCancellationRequested) return [];
    // This app registers MySQL with ';'. Preserve text if an external caller
    // supplies a custom delimiter that sql-formatter cannot safely handle.
    const delimiter = this.plugin.modelOptionsMap.get(model.id)?.delimiter;
    if (delimiter && delimiter !== ';') return [];
    const text = model.getValueInRange(range);
    try {
      const formatted = format(text, {
        language: this.dialect === 'oboracle' ? 'plsql' : 'mysql',
        tabWidth: options.tabSize,
        useTabs: !options.insertSpaces,
      });
      return formatted === text ? [] : [{ range, text: formatted }];
    } catch {
      // Incomplete SQL is normal while editing. Formatting must never erase it.
      return [];
    }
  }
}

export class DocumentFormattingEditProvider
  extends SqlFormattingProvider
  implements languages.DocumentFormattingEditProvider
{
  provideDocumentFormattingEdits(
    model: editor.ITextModel,
    options: languages.FormattingOptions,
    token: CancellationToken,
  ) {
    return this.edits(model, model.getFullModelRange(), options, token);
  }
}

export class DocumentRangeFormattingEditProvider
  extends SqlFormattingProvider
  implements languages.DocumentRangeFormattingEditProvider
{
  provideDocumentRangeFormattingEdits(
    model: editor.ITextModel,
    range: IRange,
    options: languages.FormattingOptions,
    token: CancellationToken,
  ) {
    return this.edits(model, range, options, token);
  }
}
