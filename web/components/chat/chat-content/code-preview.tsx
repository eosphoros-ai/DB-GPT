import { Button, message } from 'antd';
import { CopyOutlined } from '@ant-design/icons';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import copy from 'copy-to-clipboard';

export function CodePreview({ code, language }: { code: string; language: string }) {
  return (
    <div className="relative">
      <Button
        className="absolute right-3 top-2 text-gray-300 hover:!text-gray-200 bg-gray-700"
        type="text"
        icon={<CopyOutlined />}
        onClick={() => {
          const success = copy(code);
          message[success ? 'success' : 'error'](success ? 'Copy success' : 'Copy failed');
        }}
      />
      <SyntaxHighlighter language={language} style={oneDark}>
        {code}
      </SyntaxHighlighter>
    </div>
  );
}
