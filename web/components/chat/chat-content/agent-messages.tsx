import ReactMarkdown from 'react-markdown';
import markdownComponents from './config';
import { renderModelIcon } from '../header/model-selector';
import { SwapRightOutlined } from '@ant-design/icons';

interface Props {
  data: {
    sender: string;
    receiver: string;
    model: string | null;
    markdown: string;
  }[];
}

function AgentMessages({ data }: Props) {
  if (!data || !data.length) return null;

  return (
    <>
      {data.map((item, index) => (
        <div key={index} className="rounded my-4 md:my-6">
          <div className="flex items-center mb-3 text-sm">
            {item.model ? renderModelIcon(item.model) : <div className="rounded-full w-6 h-6 bg-gray-100" />}
            <div className="ml-2 opacity-70">
              {item.sender}
              <SwapRightOutlined className="mx-2 text-base" />
              {item.receiver}
            </div>
          </div>
          <div className="whitespace-normal text-sm">
            <ReactMarkdown components={markdownComponents}>{item.markdown}</ReactMarkdown>
          </div>
        </div>
      ))}
    </>
  );
}

export default AgentMessages;
