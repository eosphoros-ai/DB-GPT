import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getAppInfo } from '@/client/api';
import MonacoEditor from '@/components/chat/monaco-editor';
import ChatContent from '@/new-components/chat/content/ChatContent';
import { ChatContentContext } from '@/pages/chat';
import { IApp } from '@/types/app';
import { IChatDialogueMessageSchema } from '@/types/chat';
import { STORAGE_INIT_MESSAGE_KET, getInitMessage } from '@/utils';
import { useAsyncEffect } from 'ahooks';
import { Modal } from 'antd';
import { cloneDeep } from 'lodash';
import { useSearchParams } from 'next/navigation';
import React, { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { v4 as uuid } from 'uuid';

const ChatCompletion: React.FC = () => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const searchParams = useSearchParams();
  const chatId = searchParams?.get('id') ?? '';

  const { currentDialogInfo, model } = useContext(ChatContext);
  const {
    history,
    handleChat,
    refreshDialogList,
    setAppInfo,
    setModelValue,
    setTemperatureValue,
    setMaxNewTokensValue,
    setResourceValue,
  } = useContext(ChatContentContext);

  const [jsonModalOpen, setJsonModalOpen] = useState(false);
  const [jsonValue, setJsonValue] = useState<string>('');

  const showMessages = useMemo(() => {
    const tempMessage: IChatDialogueMessageSchema[] = cloneDeep(history);
    return tempMessage
      .filter(item => ['view', 'human'].includes(item.role))
      .map(item => {
        return {
          ...item,
          key: uuid(),
        };
      });
  }, [history]);

  useAsyncEffect(async () => {
    const initMessage = getInitMessage();
    if (initMessage && initMessage.id === chatId) {
      const [, res] = await apiInterceptors(
        getAppInfo({
          ...currentDialogInfo,
        }),
      );
      if (res) {
        const paramKey: string[] = res?.param_need?.map(i => i.type) || [];
        const resModel = res?.param_need?.filter(item => item.type === 'model')[0]?.value || model;
        const temperature = res?.param_need?.filter(item => item.type === 'temperature')[0]?.value || 0.6;
        const maxNewTokens = res?.param_need?.filter(item => item.type === 'max_new_tokens')[0]?.value || 4000;
        const resource = res?.param_need?.filter(item => item.type === 'resource')[0]?.bind_value;
        setAppInfo(res || ({} as IApp));
        setTemperatureValue(temperature || 0.6);
        setMaxNewTokensValue(maxNewTokens || 4000);
        setModelValue(resModel);
        setResourceValue(resource);
        await handleChat(initMessage.message, {
          app_code: res?.app_code,
          model_name: resModel,
          ...(paramKey?.includes('temperature') && { temperature }),
          ...(paramKey?.includes('max_new_tokens') && { max_new_tokens: maxNewTokens }),
          ...(paramKey.includes('resource') && {
            select_param: typeof resource === 'string' ? resource : JSON.stringify(resource),
          }),
        });
        await refreshDialogList();
        localStorage.removeItem(STORAGE_INIT_MESSAGE_KET);
      }
    }
  }, [chatId, currentDialogInfo]);

  // Track message count and user scrolling behavior
  const prevMessageCountRef = useRef(history.length);
  const lastScrollTimeRef = useRef(0);
  const isUserScrollingRef = useRef(false);
  const lastContentHeightRef = useRef(0);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isAutoScrollingRef = useRef(false); // Track if we're auto-scrolling

  // Initialize refs
  useEffect(() => {
    console.log('ChatCompletion initializing with history length:', history.length);
    // Set initial scroll time to allow streaming from the beginning
    if (lastScrollTimeRef.current === 0) {
      lastScrollTimeRef.current = Date.now() - 3000; // Set to 3 seconds ago
    }
  }, []);

  // Update message count tracking when history changes
  useEffect(() => {
    console.log('ChatCompletion updating prevMessageCountRef:', {
      currentLength: history.length,
      prevCount: prevMessageCountRef.current
    });
    
    // Only update if this is the first time (count is 0)
    if (prevMessageCountRef.current === 0) {
      prevMessageCountRef.current = history.length;
    }
  }, [history.length]);

  // Handle scroll events to detect user interaction
  const handleScrollEvent = useCallback(() => {
    // Ignore scroll events caused by auto-scrolling
    if (isAutoScrollingRef.current) {
      return;
    }
    
    lastScrollTimeRef.current = Date.now();
    
    if (scrollRef.current) {
      const scrollElement = scrollRef.current;
      const { scrollTop, scrollHeight, clientHeight } = scrollElement;
      const isAtBottom = scrollTop + clientHeight >= scrollHeight - 20;
      isUserScrollingRef.current = !isAtBottom;
    }
  }, []);

  useEffect(() => {
    if (!scrollRef.current) return;

    const scrollElement = scrollRef.current;
    const currentMessageCount = history.length;
    const isNewMessage = currentMessageCount > prevMessageCountRef.current;
    const now = Date.now();
    const userRecentlyScrolled = now - lastScrollTimeRef.current < 2000;

    console.log('ChatCompletion scroll check:', {
      currentMessageCount,
      prevCount: prevMessageCountRef.current,
      isNewMessage,
      historyLength: history.length,
      userRecentlyScrolled,
      isUserScrolling: isUserScrollingRef.current,
      isAutoScrolling: isAutoScrollingRef.current
    });

    // Always handle new messages first - this is the highest priority
    if (isNewMessage) {
      console.log('ChatCompletion: New message detected, forcing scroll to bottom');
      // New message - always scroll to bottom regardless of user position
      isAutoScrollingRef.current = true;
      
      // Reset states IMMEDIATELY to ensure streaming can work
      lastScrollTimeRef.current = Date.now() - 3000; // Allow streaming immediately
      isUserScrollingRef.current = false;
      lastContentHeightRef.current = scrollElement.scrollHeight; // Set current height as baseline
      
      scrollElement.scrollTo({
        top: scrollElement.scrollHeight,
        behavior: 'smooth',
      });
      
      // Reset auto scroll flag after animation
      setTimeout(() => {
        isAutoScrollingRef.current = false;
      }, 100);
      
      prevMessageCountRef.current = currentMessageCount; // Update count immediately
      return; // Exit early for new messages
    }
    
    // Handle streaming content updates (only if user hasn't manually scrolled recently)
    if (!userRecentlyScrolled && !isUserScrollingRef.current && !isAutoScrollingRef.current) {
      // Streaming content - scroll based on content height change
      const currentHeight = scrollElement.scrollHeight;
      
      // Initialize lastContentHeightRef if not set
      if (lastContentHeightRef.current === 0) {
        lastContentHeightRef.current = currentHeight;
      }
      
      const heightDiff = currentHeight - lastContentHeightRef.current;
      
      console.log('ChatCompletion streaming check:', {
        currentHeight,
        lastHeight: lastContentHeightRef.current,
        heightDiff,
        threshold: 12
      });
      
      // Only scroll if content height increased by at least ~0.5 lines (12px) for smoother experience
      if (heightDiff >= 12) {
        // Clear any pending scroll timeout
        if (scrollTimeoutRef.current) {
          clearTimeout(scrollTimeoutRef.current);
        }
        
        console.log('ChatCompletion: Triggering streaming scroll, heightDiff:', heightDiff);
        
        // Debounce scroll calls to avoid conflicts
        scrollTimeoutRef.current = setTimeout(() => {
          isAutoScrollingRef.current = true;
          scrollElement.scrollTo({
            top: scrollElement.scrollHeight,
            behavior: 'smooth',
          });
          setTimeout(() => {
            isAutoScrollingRef.current = false;
          }, 200); // Longer timeout for streaming scroll
          lastContentHeightRef.current = currentHeight;
        }, 30); // 30ms debounce for smooth experience
      }
    } else {
      console.log('ChatCompletion streaming blocked:', {
        userRecentlyScrolled,
        isUserScrolling: isUserScrollingRef.current,
        isAutoScrolling: isAutoScrollingRef.current
      });
    }
  }, [history]);

  // Add scroll event listener
  useEffect(() => {
    const scrollElement = scrollRef.current;
    if (scrollElement) {
      scrollElement.addEventListener('scroll', handleScrollEvent);
      return () => {
        scrollElement.removeEventListener('scroll', handleScrollEvent);
      };
    }
  }, [handleScrollEvent]);

  return (
    <div className='flex flex-col w-5/6 mx-auto' ref={scrollRef}>
      {!!showMessages.length &&
        showMessages.map((content, index) => {
          return (
            <ChatContent
              key={index}
              content={content}
              onLinkClick={() => {
                setJsonModalOpen(true);
                setJsonValue(JSON.stringify(content?.context, null, 2));
              }}
            />
          );
        })}
      <Modal
        title='JSON Editor'
        open={jsonModalOpen}
        width='60%'
        cancelButtonProps={{
          hidden: true,
        }}
        onOk={() => {
          setJsonModalOpen(false);
        }}
        onCancel={() => {
          setJsonModalOpen(false);
        }}
      >
        <MonacoEditor className='w-full h-[500px]' language='json' value={jsonValue} />
      </Modal>
    </div>
  );
};

export default ChatCompletion;
