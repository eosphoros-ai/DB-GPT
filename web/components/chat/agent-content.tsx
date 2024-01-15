import { ChatContext } from '@/app/chat-context';
import { IChatDialogueMessageSchema } from '@/types/chat';
import classNames from 'classnames';
import { memo, useContext } from 'react';
import ReactMarkdown from 'react-markdown';

interface Props {
  content: IChatDialogueMessageSchema;
}

function formatMarkdownVal(val: string) {
  return val.replace(/<table(\w*=[^>]+)>/gi, '<table $1>').replace(/<tr(\w*=[^>]+)>/gi, '<tr $1>');
}

function AgentContent({ content }: Props) {
  const { scene } = useContext(ChatContext);

  const isView = content.role === 'view';

  return (
    <div
      className={classNames('relative flex flex-wrap w-full p-2 md:p-4 rounded-xl break-words', {
        'bg-white dark:bg-[#232734]': isView,
        'lg:w-full xl:w-full pl-0': ['chat_with_db_execute', 'chat_dashboard'].includes(scene),
      })}
    >
      {isView ? <ReactMarkdown>{formatMarkdownVal(content.context)}</ReactMarkdown> : <div className="">{content.context}</div>}
    </div>
  );
}

export default memo(AgentContent);
