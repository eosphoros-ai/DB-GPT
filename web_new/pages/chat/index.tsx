import React, { useContext, useEffect } from 'react';
import { useRouter } from 'next/router';
import { ChatContext } from '@/app/chat-context';
import dynamic from 'next/dynamic';

const DbEditor = dynamic(() => import('@/components/chat/db-editor'), { ssr: false });
const ChatContainer = dynamic(() => import('@/components/chat/chat-container'), { ssr: false });

function Chat() {
  const {
    query: { id, scene },
  } = useRouter();
  const { isContract, setIsContract, setIsMenuExpand } = useContext(ChatContext);

  useEffect(() => {
    // 仅初始化执行，防止dashboard页面无法切换状态
    setIsMenuExpand(scene !== 'chat_dashboard');
    // 路由变了要取消Editor模式，再进来是默认的Preview模式
    if (id && scene) {
      setIsContract(false);
    }
  }, [id, scene]);

  return <>{isContract ? <DbEditor /> : <ChatContainer />}</>;
}

export default Chat;
