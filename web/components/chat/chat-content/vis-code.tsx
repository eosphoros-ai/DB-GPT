import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import markdownComponents from './config';
import { CodePreview } from './code-preview';
import classNames from 'classnames';
import { useState } from 'react';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { oneLight, oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface Props {
  data: {
    code: string[];
    exit_success: true;
    language: string;
    log: string;
  };
}

function VisCode({ data }: Props) {
  const { t } = useTranslation();

  const [show, setShow] = useState(0);

  return (
    <div className="bg-[#EAEAEB] rounded overflow-hidden border border-theme-primary dark:bg-theme-dark text-sm">
      <div>
        <div className="flex">
          {data.code.map((item, index) => (
            <div
              key={index}
              className={classNames('px-4 py-2 text-[#121417] dark:text-white cursor-pointer', {
                'bg-white dark:bg-theme-dark-container': index === show,
              })}
              onClick={() => {
                setShow(index);
              }}
            >
              CODE {index + 1}: {item[0]}
            </div>
          ))}
        </div>
        {data.code.length && (
          <CodePreview
            language={data.code[show][0]}
            code={data.code[show][1]}
            customStyle={{ maxHeight: 300, margin: 0 }}
            light={oneLight}
            dark={oneDark}
          />
        )}
      </div>
      <div>
        <div className="flex">
          <div className="bg-white dark:bg-theme-dark-container px-4 py-2 text-[#121417] dark:text-white">
            {t('Terminal')} {data.exit_success ? <CheckOutlined className="text-green-600" /> : <CloseOutlined className="text-red-600" />}
          </div>
        </div>
        <div className="p-4 max-h-72 overflow-y-auto whitespace-normal bg-white dark:dark:bg-theme-dark">
          <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]}>
            {data.log}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
}

export default VisCode;
