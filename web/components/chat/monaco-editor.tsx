import { ChatContext } from '@/app/chat-context';
import { formatSql } from '@/utils';
import Editor, { OnChange, loader } from '@monaco-editor/react';
import { useLatest } from 'ahooks';
import classNames from 'classnames';
import * as monaco from 'monaco-editor/esm/vs/editor/editor.api.js';
import { useContext, useMemo } from 'react';
import { register } from './ob-editor/ob-plugin';
import { getModelService } from './ob-editor/service';
import { github, githubDark } from './ob-editor/theme';

loader.config({ monaco });

export interface ISession {
  getTableList: (schemaName?: string) => Promise<string[]>;
  getTableColumns: (tableName: string) => Promise<{ columnName: string; columnType: string }[]>;
  getSchemaList: () => Promise<string[]>;
}

interface MonacoEditorProps {
  className?: string;
  value: string;
  language: string;
  onChange?: OnChange;
  thoughts?: string;
  session?: ISession;
}

monaco.editor.defineTheme('github', github as any);
monaco.editor.defineTheme('githubDark', githubDark as any);

export default function MonacoEditor({
  className,
  value,
  language = 'mysql',
  onChange,
  thoughts,
  session,
}: MonacoEditorProps) {
  // merge value and thoughts

  const editorValue = useMemo(() => {
    if (language !== 'mysql') {
      return value;
    }
    if (thoughts && thoughts.length > 0) {
      return formatSql(`-- ${thoughts} \n${value}`);
    }
    return formatSql(value);
  }, [value, thoughts]);

  const sessionRef = useLatest(session);

  const context = useContext(ChatContext);

  async function pluginRegister(editor: monaco.editor.IStandaloneCodeEditor) {
    const plugin = await register();
    plugin.setModelOptions(
      editor.getModel()?.id || '',
      getModelService(
        {
          modelId: editor.getModel()?.id || '',
          delimiter: ';',
        },
        () => sessionRef.current || null,
      ),
    );
  }

  return (
    <Editor
      className={classNames(className)}
      onMount={pluginRegister}
      value={editorValue}
      defaultLanguage={language}
      onChange={onChange}
      theme={context?.mode !== 'dark' ? 'github' : 'githubDark'}
      options={{
        minimap: {
          enabled: false,
        },
        wordWrap: 'on',
      }}
    />
  );
}
