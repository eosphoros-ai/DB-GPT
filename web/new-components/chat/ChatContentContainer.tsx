import ChatHeader from '@/new-components/chat/header/ChatHeader';
import { ChatContentContext } from '@/pages/chat';
import { VerticalAlignBottomOutlined, VerticalAlignTopOutlined } from '@ant-design/icons';
import dynamic from 'next/dynamic';
import React, {
  forwardRef,
  useCallback,
  useContext,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';

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
  const scrollToBottomSmooth = useCallback((forceScroll = false) => {
    if (!scrollRef.current) return;

    // For force scroll (new messages), bypass allowAutoScroll check
    if (!forceScroll && !allowAutoScroll.current) return;

    const container = scrollRef.current;
    const { scrollTop, scrollHeight, clientHeight } = container;

    // Only auto-scroll when user is near bottom, unless force scroll is requested
    const buffer = Math.max(50, clientHeight * 0.1);
    const isNearBottom = scrollTop + clientHeight >= scrollHeight - buffer;

    if (!isNearBottom && !forceScroll) {
      return;
    }

    // Clear previous animation frame to prevent memory leaks
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }

    // Use requestAnimationFrame but with instant scroll to avoid animation conflicts
    animationFrameRef.current = requestAnimationFrame(() => {
      if (scrollRef.current) {
        scrollRef.current.scrollTo({
          top: scrollRef.current.scrollHeight,
          behavior: forceScroll ? 'smooth' : 'auto', // Smooth only for new messages, instant for streaming
        });
      }
      animationFrameRef.current = null;
    });
  }, []);

  // Optimize last message tracking to reduce unnecessary re-renders
  const lastMessage = useMemo(() => {
    const last = history[history.length - 1];
    return last ? { context: last.context, thinking: last.thinking } : null;
  }, [history]); // Track previous history length to detect new messages
  const prevHistoryLengthRef = useRef(history.length);

  useEffect(() => {
    const currentHistoryLength = history.length;
    const isNewMessage = currentHistoryLength > prevHistoryLengthRef.current;

    if (isNewMessage) {
      // Force scroll to bottom when new message is added
      scrollToBottomSmooth(true);
      prevHistoryLengthRef.current = currentHistoryLength;
    } else {
      // For streaming content updates, only scroll if user is near bottom
      scrollToBottomSmooth(false);
    }
  }, [history.length, scrollToBottomSmooth]);

  // Handle streaming content updates separately to avoid multiple scroll calls
  useEffect(() => {
    // Only trigger scroll for content changes, not for new messages
    if (history.length === prevHistoryLengthRef.current) {
      scrollToBottomSmooth(false);
    }
  }, [lastMessage?.context, lastMessage?.thinking, history.length, scrollToBottomSmooth]);

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
        <div className='absolute right-4 md:right-6 bottom-[120px] md:bottom-[100px] flex flex-col gap-2 z-[999]'>
          {!isAtTop && (
            <button
              onClick={scrollToTop}
              className='w-9 h-9 md:w-10 md:h-10 bg-white dark:bg-[rgba(255,255,255,0.2)] border border-gray-200 dark:border-[rgba(255,255,255,0.2)] rounded-full flex items-center justify-center shadow-md hover:shadow-lg transition-all duration-200'
              aria-label='Scroll to top'
            >
              <VerticalAlignTopOutlined className='text-[#525964] dark:text-[rgba(255,255,255,0.85)] text-sm md:text-base' />
            </button>
          )}
          {!isAtBottom && (
            <button
              onClick={scrollToBottom}
              className='w-9 h-9 md:w-10 md:h-10 bg-white dark:bg-[rgba(255,255,255,0.2)] border border-gray-200 dark:border-[rgba(255,255,255,0.2)] rounded-full flex items-center justify-center shadow-md hover:shadow-lg transition-all duration-200'
              aria-label='Scroll to bottom'
            >
              <VerticalAlignBottomOutlined className='text-[#525964] dark:text-[rgba(255,255,255,0.85)] text-sm md:text-base' />
            </button>
          )}
        </div>
      )}
    </div>
  );
};

export default forwardRef(ChatContentContainer);
