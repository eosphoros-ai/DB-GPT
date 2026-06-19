import React, { memo, useContext, useMemo } from 'react';
import { MobileChatContext } from '../';
import ChatDialog from './ChatDialog';

const Content: React.FC = () => {
  const { history } = useContext(MobileChatContext);

  // Filter messages to display
  const showMessages = useMemo(() => {
    return history.filter(item => ['view', 'human'].includes(item.role));
  }, [history]);

  return (
    <div className='flex flex-col gap-4'>
      {!!showMessages.length &&
        showMessages.map((message, index) => {
          return <ChatDialog key={message.context + index} message={message} index={index} />;
        })}
    </div>
  );
};

export default memo(Content);
