import { ChatContext } from '@/app/chat-context';
import { CopyOutlined } from '@ant-design/icons';
import { Button, message } from 'antd';
import copy from 'copy-to-clipboard';
import { CSSProperties, useContext } from 'react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { coldarkDark, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { useTranslation } from 'react-i18next';

interface Props {
  code: string;
  language: string;
  customStyle?: CSSProperties;
  light?: { [key: string]: CSSProperties };
  dark?: { [key: string]: CSSProperties };
}

export function CodePreview({
  const { t } = useTranslation(); code, light, dark, language, customStyle }: Props) {
  const { mode } = useContext(ChatContext);

  return (
    <div className='relative'>
      <Button
        className='absolute right-3 top-2 text-gray-300 hover:!text-gray-200 bg-gray-700'
        type='text'
        icon={<CopyOutlined />}
        onClick={() => {
          const success = copy(code);
          message[success ? 'success' : 'error'](success ? t('copy_success') : t('copy_failed_generic'));
        }}
      />
      <SyntaxHighlighter
        customStyle={{ ...customStyle, maxHeight: '400px', overflow: 'auto' }}
        language={language}
        style={mode === 'dark' ? (dark ?? coldarkDark) : (light ?? oneDark)}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
