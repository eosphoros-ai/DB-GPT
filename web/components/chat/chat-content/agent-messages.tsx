import ReactMarkdown from 'react-markdown';
import markdownComponents from './config';
import { renderModelIcon } from '../header/model-selector';

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
        <div key={index} className="bg-white py-3 px-4 rounded my-3 dark:bg-[#212121]">
          <div className="flex items-center mb-4 text-sm">
            {item.model ? renderModelIcon(item.model) : <div className="rounded-full w-6 h-6 bg-gray-100" />}
            <div className="ml-2 opacity-70">{`${item.sender} -> ${item.receiver}`}</div>
          </div>
          <ReactMarkdown components={markdownComponents}>{item.markdown}</ReactMarkdown>
        </div>
      ))}
    </>
  );
}

export default AgentMessages;
