import { ChatContext } from '@/app/chat-context';
import { IChatDialogueMessageSchema } from '@/types/chat';
import classNames from 'classnames';
import { memo, useContext } from 'react';
import { GPTVis } from '@antv/gpt-vis';
import markdownComponents from './chat-content/config';
import rehypeRaw from 'rehype-raw';

interface Props {
  content: IChatDialogueMessageSchema;
}

function formatMarkdownVal(val: string) {
  return val?.replace(/<table(\w*=[^>]+)>/gi, '<table $1>').replace(/<tr(\w*=[^>]+)>/gi, '<tr $1>');
}

function AgentContent({ content }: Props) {
  const { scene } = useContext(ChatContext);

  const isView = content.role === 'view';

  return (
    <div
      className={classNames(
        "relative w-full p-2 md:p-4 rounded-xl break-words",
        {
          "bg-white dark:bg-[#232734]": isView,
          "lg:w-full xl:w-full pl-0": [
            "chat_with_db_execute",
            "chat_dashboard",
          ].includes(scene),
        }
      )}
    >
      {isView ? (
        <GPTVis components={markdownComponents} rehypePlugins={[rehypeRaw]}>
          {formatMarkdownVal(content.context)}
        </GPTVis>
      ) : (
        <div className="">{content.context}</div>
      )}
    </div>
  );
}

export default memo(AgentContent);
