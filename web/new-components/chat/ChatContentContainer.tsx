import ChatHeader from '@/new-components/chat/header/ChatHeader';
import { ChatContentContext } from '@/pages/chat';
import { VerticalAlignBottomOutlined, VerticalAlignTopOutlined } from '@ant-design/icons';
import dynamic from 'next/dynamic';
import React, { forwardRef, useCallback, useContext, useEffect, useImperativeHandle, useRef, useState, useMemo } from 'react';

const ChatCompletion = dynamic(() => import('@/new-components/chat/content/ChatCompletion'), { ssr: false });

// eslint-disable-next-line no-empty-pattern
const ChatContentContainer = ({ className }: { className?: string }, ref: React.ForwardedRef<any>) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isScrollToTop, setIsScrollToTop] = useState<boolean>(false);
  const [showScrollButtons, setShowScrollButtons] = useState<boolean>(false);
  const [isAtTop, setIsAtTop] = useState<boolean>(true);
  const [isAtBottom, setIsAtBottom] = useState<boolean>(false);
  const { history } = useContext(ChatContentContext);
  const allowAutoScroll = useRef<boolean>(true);
  const animationFrameRef = useRef<number | null>(null);

  useImperativeHandle(ref, () => {
    return scrollRef.current;
  });

  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;

    const container = scrollRef.current;
    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight;
    const clientHeight = container.clientHeight;
    const buffer = 20;

    // Check Scroll direction
    const lastScrollTop = Number(container?.dataset?.lastScrollTop) || 0;
    const direction = scrollTop > lastScrollTop ? 'down' : 'up';
    container.dataset.lastScrollTop = String(scrollTop);
    // only allow auto scroll when user is near bottom
    allowAutoScroll.current = direction === 'down';

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
  }, []);

  useEffect(() => {
    const currentScrollRef = scrollRef.current;
    if (currentScrollRef) {
      currentScrollRef.addEventListener('scroll', handleScroll);

      // Check initially if content is scrollable
      const isScrollable = currentScrollRef.scrollHeight > currentScrollRef.clientHeight;
      setShowScrollButtons(isScrollable);
    }

    return () => {
      if (currentScrollRef) {
        currentScrollRef.removeEventListener('scroll', handleScroll);
      }
    };
  }, [handleScroll]);

  const scrollToBottomSmooth = useCallback(() => {
    if (!scrollRef.current || !allowAutoScroll.current) return;

    const container = scrollRef.current;
    const { scrollTop, scrollHeight, clientHeight } = container;

    // Only auto-scroll when user is near bottom
    const buffer = Math.max(50, clientHeight * 0.1);
    const isNearBottom = scrollTop + clientHeight >= scrollHeight - buffer;

    if (!isNearBottom) {
      return;
    }

    // Clear previous animation frame to prevent memory leaks
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    // use requestAnimationFrame to smooth scroll
    animationFrameRef.current = requestAnimationFrame(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTo({
          top: scrollRef.current.scrollHeight,
          behavior: 'auto',
        });
      }
      animationFrameRef.current = null;
    });
  }, []);

  // Optimize last message tracking to reduce unnecessary re-renders
  const lastMessage = useMemo(() => {
    const last = history[history.length - 1];
    return last ? { context: last.context, thinking: last.thinking } : null;
  }, [history]);

  useEffect(() => {
    // Listen for history changes and last message context/thinking changes
    scrollToBottomSmooth();
  }, [history.length, lastMessage?.context, lastMessage?.thinking, scrollToBottomSmooth]);

  // Cleanup animation frame on unmount
  useEffect(() => {
    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  const scrollToTop = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: 0,
        behavior: 'smooth',
      });
    }
  }, []);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: 'smooth',
      });
    }
  }, []);

  return (
    <div className={`flex flex-1 overflow-hidden relative ${className || ''}`}>
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
