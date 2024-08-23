import { ChatContext } from '@/app/chat-context';
import { LoadingOutlined } from '@ant-design/icons';
import JsonView from '@uiw/react-json-view';
import { githubDarkTheme } from '@uiw/react-json-view/githubDark';
import { githubLightTheme } from '@uiw/react-json-view/githubLight';
import { Alert, Spin } from 'antd';
import classNames from 'classnames';
import React, { useContext, useMemo } from 'react';
import { GPTVis } from '@antv/gpt-vis'; 
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';

import markdownComponents from './config';

interface VisResponseProps {
  name: string;
  args: any;
  status: string;
  logo: string;
  result: string;
  err_msg: any;
}

const VisResponse: React.FC<{ data: VisResponseProps }> = ({ data }) => {
  const { mode } = useContext(ChatContext);
  const type = useMemo(() => {
    switch (data.status) {
      case 'complete':
        return 'success';
      case 'failed':
        return 'error';
      case 'running':
        return 'warning';
      default:
        undefined;
    }
  }, [data]);
  if (!data) return null;
  const theme = mode === 'dark' ? githubDarkTheme : githubLightTheme;

  return (
    <div className="flex flex-1 flex-col">
      <Alert
        className={classNames("mb-4", {
          "bg-[#fafafa] border-[transparent]": !type,
        })}
        message={data.name}
        type={type}
        {...(type && { showIcon: true })}
        {...(type === "warning" && {
          icon: <Spin indicator={<LoadingOutlined spin />} />,
        })}
      />
      {data.result && (
        <JsonView
          style={{ ...theme, width: "100%", padding: 10 }}
          className={classNames({
            "bg-[#fafafa]": mode === "light",
          })}
          value={JSON.parse(data.result || "{}")}
          enableClipboard={false}
          displayDataTypes={false}
          objectSortKeys={false}
        />
      )}
      {data.err_msg && (
        <GPTVis
          components={markdownComponents}
          remarkPlugins={[remarkGfm]}
          rehypePlugins={[rehypeRaw]}
        >
          {data.err_msg}
        </GPTVis>
      )}
    </div>
  );
};

export default VisResponse;
