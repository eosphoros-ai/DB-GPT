import ChatHeader from '@/new-components/chat/header/ChatHeader';
import { ChatContentContext } from '@/pages/chat';
import { VerticalAlignBottomOutlined, VerticalAlignTopOutlined } from '@ant-design/icons';
import dynamic from 'next/dynamic';
import React, { forwardRef, useCallback, useContext, useEffect, useImperativeHandle, useRef, useState } from 'react';

const ChatCompletion = dynamic(() => import('@/new-components/chat/content/ChatCompletion'), { ssr: false });

// eslint-disable-next-line no-empty-pattern
const ChatContentContainer = ({}, ref: React.ForwardedRef<any>) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isScrollToTop, setIsScrollToTop] = useState<boolean>(false);
  const [showScrollButtons, setShowScrollButtons] = useState<boolean>(false);
  const [isAtTop, setIsAtTop] = useState<boolean>(true);
  const [isAtBottom, setIsAtBottom] = useState<boolean>(false);
  const { history } = useContext(ChatContentContext);
  const wasAtBottomRef = useRef<boolean>(true); // Initialize to true, assuming user starts at bottom

  useImperativeHandle(ref, () => {
    return scrollRef.current;
  });

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

  const scrollToBottomSmooth = useCallback((force = false, isStreaming = false) => {
    if (!scrollRef.current) return;

    const container = scrollRef.current;
    
    if (force) {
      // Force scroll for new messages - always scroll regardless of position
      container.scrollTo({
        top: container.scrollHeight,
        behavior: 'smooth',
      });
      return;
    }

    // For streaming updates, check if user is near bottom
    const { scrollTop, scrollHeight, clientHeight } = container;
    const buffer = Math.max(100, clientHeight * 0.2);
    const isNearBottom = scrollTop + clientHeight >= scrollHeight - buffer;

    if (!isNearBottom) {
      return;
    }

    // Use smooth scroll for streaming updates
    container.scrollTo({
      top: container.scrollHeight,
      behavior: 'smooth',
    });
  }, []);

  // Track message count to detect new messages
  const prevMessageCountRef = useRef(history.length);
  const lastScrollTimeRef = useRef(0);
  const isUserScrollingRef = useRef(false);
  const lastContentHeightRef = useRef(0);
  const scrollTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isAutoScrollingRef = useRef(false); // Track if we're auto-scrolling

  // Initialize refs
  useEffect(() => {
    console.log('ChatContentContainer initializing with history length:', history.length);
    // Set initial scroll time to allow streaming from the beginning
    if (lastScrollTimeRef.current === 0) {
      lastScrollTimeRef.current = Date.now() - 3000; // Set to 3 seconds ago
    }
  }, []);

  // Update message count tracking when history changes
  useEffect(() => {
    console.log('ChatContentContainer updating prevMessageCountRef:', {
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
    
    console.log('ChatContentContainer scroll check:', {
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
      console.log('ChatContentContainer: New message detected, forcing scroll to bottom');
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
      
      console.log('ChatContentContainer streaming check:', {
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
        
        console.log('ChatContentContainer: Triggering streaming scroll, heightDiff:', heightDiff);
        
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
      console.log('ChatContentContainer streaming blocked:', {
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

  // Enhanced scroll handler to track user scrolling behavior
  const handleScroll = useCallback(() => {
    if (!scrollRef.current) return;

    const container = scrollRef.current;
    const scrollTop = container.scrollTop;
    const scrollHeight = container.scrollHeight;
    const clientHeight = container.clientHeight;
    const buffer = 20;

    // Record user scroll time
    lastScrollTimeRef.current = Date.now();
    
    // Determine if user is actively scrolling up
    const atBottom = scrollTop + clientHeight >= scrollHeight - buffer;
    isUserScrollingRef.current = !atBottom;

    // Update wasAtBottomRef
    const atBottomPrecise = scrollTop + clientHeight >= scrollHeight - 5;
    wasAtBottomRef.current = atBottomPrecise;

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
    <div className='flex flex-1 relative'>
      <div 
        ref={scrollRef} 
        className='h-full w-full mx-auto overflow-y-auto'
        style={{ scrollBehavior: 'smooth' }}
      >
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
