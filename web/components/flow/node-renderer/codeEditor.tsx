import React, { useState, useMemo } from 'react';
import { Button, Modal } from 'antd';
import Editor from '@monaco-editor/react';
import { IFlowNodeParameter } from '@/types/flow';
// import { MonacoEditor } from '../../chat/monaco-editor';
// import { github, githubDark } from './ob-editor/theme';
import { github, githubDark } from '../../chat/ob-editor/theme';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderCodeEditor = (params: Props) => {
  const { data, defaultValue, onChange } = params;

  const [isModalOpen, setIsModalOpen] = useState(false);
  const showModal = () => {
    setIsModalOpen(true);
  };

  const handleOk = () => {
    setIsModalOpen(false);
  };

  const handleCancel = () => {
    setIsModalOpen(false);
  };
  /**
   * 设置弹窗宽度
   */
  const modalWidth = useMemo(() => {
    if (data?.ui?.editor?.width) {
      return data?.ui?.editor?.width + 100
    }
    return '80%';
  }, [data?.ui?.editor?.width]);

  return (
    <div style={{textAlign:'center'}} className="p-2 text-sm">
      <Button type="primary" onClick={showModal}>
        打开代码编辑器
      </Button>
      <Modal title="代码编辑:" width={modalWidth} open={isModalOpen} onOk={handleOk} onCancel={handleCancel}>
        <Editor
          {...data?.ui?.attr}
          width={data?.ui?.editor?.width || '100%'}
          value={defaultValue}
          style={{padding:'10px'}}
          height={data?.ui?.editor?.height || 200}
          defaultLanguage={data?.ui?.language}
          onChange={onChange}
          theme='vs-dark' // 编辑器主题颜色
          options={{
            minimap: {
              enabled: false,
            },
            wordWrap: 'on',
          }}
        />

        {/* <Editor
          {...data?.ui?.attr}
          language={data?.ui?.language}
          width={data?.ui?.editor?.width || '100%'}
          value={defaultValue}
          height={data?.ui?.editor?.height || 200}
          defaultValue={defaultValue}
          onChange={(value: string | undefined) => {
            console.log(value);
            onChange(value)
          }}
          options={{
            theme: {github}, // 编辑器主题颜色
            folding: true, // 是否折叠
            foldingHighlight: true, // 折叠等高线
            foldingStrategy: 'indentation', // 折叠方式  auto | indentation
            showFoldingControls: 'always', // 是否一直显示折叠 always | mouseover
            disableLayerHinting: true, // 等宽优化
            emptySelectionClipboard: false, // 空选择剪切板
            selectionClipboard: false, // 选择剪切板
            automaticLayout: true, // 自动布局
            codeLens: false, // 代码镜头
            scrollBeyondLastLine: false, // 滚动完最后一行后再滚动一屏幕
            colorDecorators: true, // 颜色装饰器
            accessibilitySupport: 'auto', // 辅助功能支持  "auto" | "off" | "on"
            lineNumbers: 'on', // 行号 取值： "on" | "off" | "relative" | "interval" | function
            lineNumbersMinChars: 5, // 行号最小字符   number
            readOnly: false, //是否只读  取值 true | false
          }}
        /> */}
      </Modal>

    </div>
  );
};
