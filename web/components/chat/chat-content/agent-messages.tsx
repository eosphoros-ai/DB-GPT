import ModelIcon from '@/new-components/chat/content/ModelIcon';
import { LinkOutlined, SwapRightOutlined } from '@ant-design/icons';
import { Popover, Space } from 'antd';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import markdownComponents from './config';
import ReferencesContent from './ReferencesContent';

interface Props {
  data: {
    sender: string;
    receiver: string;
    model: string | null;
    markdown: string;
    resource: any;
  }[];
}

function AgentMessages({ data }: Props) {
  if (!data || !data.length) return null;
  return (
    <>
      {data.map((item, index) => (
        <div key={index} className="rounded">
          <div className="flex items-center mb-3 text-sm">
            {item.model ? <ModelIcon model={item.model} /> : <div className="rounded-full w-6 h-6 bg-gray-100" />}
            <div className="ml-2 opacity-70">
              {item.sender}
              <SwapRightOutlined className="mx-2 text-base" />
              {item.receiver}
            </div>
          </div>
          <div className="whitespace-normal text-sm mb-3">
            <ReactMarkdown components={markdownComponents} remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
              {item.markdown}
            </ReactMarkdown>
          </div>
          {item.resource && item.resource !== 'null' && <ReferencesContent references={item.resource} />}
        </div>
      ))}
    </>
  );
}

export default AgentMessages;
