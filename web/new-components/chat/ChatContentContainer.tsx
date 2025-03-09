import ChatHeader from '@/new-components/chat/header/ChatHeader';
import { VerticalAlignBottomOutlined, VerticalAlignTopOutlined } from '@ant-design/icons';
import dynamic from 'next/dynamic';
import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';

const ChatCompletion = dynamic(() => import('@/new-components/chat/content/ChatCompletion'), { ssr: false });

// eslint-disable-next-line no-empty-pattern
const ChatContentContainer = ({}, ref: React.ForwardedRef<any>) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isScrollToTop, setIsScrollToTop] = useState<boolean>(false);
  const [showScrollButtons, setShowScrollButtons] = useState<boolean>(false);
  const [isAtTop, setIsAtTop] = useState<boolean>(true);
  const [isAtBottom, setIsAtBottom] = useState<boolean>(false);

  useImperativeHandle(ref, () => {
    return scrollRef.current;
  });

  const handleScroll = () => {
    if (!scrollRef.current) return;

    const container = scrollRef.current;
    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight;
    const clientHeight = container.clientHeight;
    const buffer = 20; // Small buffer for better UX

    // Check if we're at the top
    setIsAtTop(scrollTop <= buffer);

    // Check if we're at the bottom
    setIsAtBottom(scrollTop + clientHeight >= scrollHeight - buffer);

    // Header visibility
    if (scrollTop >= 42 + 32) {
      setIsScrollToTop(true);
    } else {
      setIsScrollToTop(false);
    }

    // Show scroll buttons when content is scrollable
    const isScrollable = scrollHeight > clientHeight;
    setShowScrollButtons(isScrollable);
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.addEventListener('scroll', handleScroll);

      // Check initially if content is scrollable
      const isScrollable = scrollRef.current.scrollHeight > scrollRef.current.clientHeight;
      setShowScrollButtons(isScrollable);
    }

    return () => {
      // eslint-disable-next-line react-hooks/exhaustive-deps
      scrollRef.current && scrollRef.current.removeEventListener('scroll', handleScroll);
    };
  }, []);

  const scrollToTop = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: 0,
        behavior: 'smooth',
      });
    }
  };

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  };

  return (
    <div className='flex flex-1 overflow-hidden relative'>
      <div ref={scrollRef} className='h-full w-full mx-auto overflow-y-auto'>
        <ChatHeader isScrollToTop={isScrollToTop} />
        <ChatCompletion />
      </div>

      {showScrollButtons && (
        <div className='absolute right-6 bottom-24 flex flex-col gap-2'>
          {!isAtTop && (
            <button
              onClick={scrollToTop}
              className='w-10 h-10 bg-white dark:bg-[rgba(255,255,255,0.2)] border border-gray-200 dark:border-[rgba(255,255,255,0.2)] rounded-full flex items-center justify-center shadow-md hover:shadow-lg transition-shadow'
              aria-label='Scroll to top'
            >
              <VerticalAlignTopOutlined className='text-[#525964] dark:text-[rgba(255,255,255,0.85)]' />
            </button>
          )}
          {!isAtBottom && (
            <button
              onClick={scrollToBottom}
              className='w-10 h-10 bg-white dark:bg-[rgba(255,255,255,0.2)] border border-gray-200 dark:border-[rgba(255,255,255,0.2)] rounded-full flex items-center justify-center shadow-md hover:shadow-lg transition-shadow'
              aria-label='Scroll to bottom'
            >
              <VerticalAlignBottomOutlined className='text-[#525964] dark:text-[rgba(255,255,255,0.85)]' />
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default forwardRef(ChatContentContainer);
