import { ChatContext } from '@/app/chat-context';
import { CopyOutlined } from '@ant-design/icons';
import { Button, message } from 'antd';
import copy from 'copy-to-clipboard';
import { CSSProperties, useContext } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { coldarkDark, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface Props {
  code: string;
  language: string;
  customStyle?: CSSProperties;
  codeStyle?: CSSProperties;
  light?: { [key: string]: CSSProperties };
  dark?: { [key: string]: CSSProperties };
}

export function CodePreview({ code, light, dark, language, customStyle, codeStyle }: Props) {
  const { mode } = useContext(ChatContext);

  return (
    <div className='relative'>
      <Button
        className='absolute right-3 top-2 text-gray-300 hover:!text-gray-200 bg-gray-700'
        type='text'
        icon={<CopyOutlined />}
        onClick={() => {
          const success = copy(code);
          message[success ? 'success' : 'error'](success ? '复制成功' : '复制失败');
        }}
      />
      <SyntaxHighlighter
        customStyle={{ ...customStyle, maxHeight: '400px', overflow: 'auto' }}
        codeTagProps={codeStyle ? { style: codeStyle } : undefined}
        language={language}
        style={mode === 'dark' ? (dark ?? coldarkDark) : (light ?? oneDark)}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
