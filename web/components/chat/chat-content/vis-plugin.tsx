import { CheckOutlined, ClockCircleOutlined, CloseOutlined, LoadingOutlined } from '@ant-design/icons';
import classNames from 'classnames';
import { ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import markdownComponents from './config';
import rehypeRaw from 'rehype-raw';

interface IVisPlugin {
  name: string;
  args: {
    query: string;
  };
  status: 'todo' | 'runing' | 'failed' | 'complete' | (string & {});
  logo: string | null;
  result: string;
  err_msg: string | null;
}

interface Props {
  data: IVisPlugin;
}

const pluginViewStatusMapper: Record<IVisPlugin['status'], { bgClass: string; icon: ReactNode }> = {
  todo: {
    bgClass: 'bg-gray-500',
    icon: <ClockCircleOutlined className="ml-2" />,
  },
  runing: {
    bgClass: 'bg-blue-500',
    icon: <LoadingOutlined className="ml-2" />,
  },
  failed: {
    bgClass: 'bg-red-500',
    icon: <CloseOutlined className="ml-2" />,
  },
  complete: {
    bgClass: 'bg-green-500',
    icon: <CheckOutlined className="ml-2" />,
  },
};

function VisPlugin({ data }: Props) {
  const { bgClass, icon } = pluginViewStatusMapper[data.status] ?? {};

  return (
    <div className="bg-theme-light dark:bg-theme-dark-container rounded overflow-hidden my-2 flex flex-col lg:max-w-[80%]">
      <div className={classNames('flex px-4 md:px-6 py-2 items-center text-white text-sm', bgClass)}>
        {data.name}
        {icon}
      </div>
      {data.result ? (
        <div className="px-4 md:px-6 py-4 text-sm whitespace-normal">
          <ReactMarkdown components={markdownComponents} rehypePlugins={[rehypeRaw]}>
            {data.result ?? ''}
          </ReactMarkdown>
        </div>
      ) : (
        <div className="px-4 md:px-6 py-4 text-sm">{data.err_msg}</div>
      )}
    </div>
  );
}

export default VisPlugin;
