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

  // Initial UI state setup
  useEffect(() => {
    if (scrollRef.current) {
      // Check initially if content is scrollable
      const isScrollable = scrollRef.current.scrollHeight > scrollRef.current.clientHeight;
      setShowScrollButtons(isScrollable);
    }
  }, []);

  // Track message count and user scrolling behavior
  const prevMessageCountRef = useRef(0); // Always start from 0 to detect first message correctly
  const isUserScrollingRef = useRef(false);
  const lastContentHeightRef = useRef(0);
  const isStreamingRef = useRef(false); // Track if we're in streaming mode
  const streamingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const mutationObserverRef = useRef<MutationObserver | null>(null);
  const backupIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Initialize refs with current history length
  useEffect(() => {
    console.log('ChatContentContainer initializing with history length:', history.length);
    // Set initial message count to current history length (to avoid triggering new message on first render)
    prevMessageCountRef.current = history.length;
  }, []); // No dependencies - only run once

  // Combined scroll event handler for both streaming logic and UI state
  const handleScrollEvent = useCallback(() => {
    if (!scrollRef.current) return;

    const scrollElement = scrollRef.current;
    const { scrollTop, scrollHeight, clientHeight } = scrollElement;
    const buffer = 20;

    // UI state updates (for scroll buttons and header visibility)
    const atBottomPrecise = scrollTop + clientHeight >= scrollHeight - 5;
    wasAtBottomRef.current = atBottomPrecise;

    setIsAtTop(scrollTop <= buffer);
    setIsAtBottom(scrollTop + clientHeight >= scrollHeight - buffer);

    if (scrollTop >= 42 + 32) {
      setIsScrollToTop(true);
    } else {
      setIsScrollToTop(false);
    }

    const isScrollable = scrollHeight > clientHeight;
    setShowScrollButtons(isScrollable);

    // Streaming logic - only update user scroll state when not in streaming mode
    if (!isStreamingRef.current) {
      const isAtBottom = scrollTop + clientHeight >= scrollHeight - 5;
      const wasUserScrolling = isUserScrollingRef.current;
      isUserScrollingRef.current = !isAtBottom;

      if (wasUserScrolling !== isUserScrollingRef.current) {
        console.log('ChatContentContainer: User scroll state changed:', {
          isAtBottom,
          isUserScrolling: isUserScrollingRef.current,
          scrollTop,
          scrollHeight,
          clientHeight,
        });
      }
    } else {
      console.log('ChatContentContainer: Ignoring scroll event during streaming');
    }
  }, []);

  // Simple and reliable scroll function
  const scrollToBottomInstant = useCallback(() => {
    if (!scrollRef.current) return;

    const scrollElement = scrollRef.current;
    console.log('ChatContentContainer: Scrolling to bottom');

    // Use instant scroll to avoid animation-related event conflicts
    scrollElement.scrollTo({
      top: scrollElement.scrollHeight,
      behavior: 'instant',
    });
  }, []);

  // Check for height changes and handle streaming scroll
  const checkContentHeight = useCallback(() => {
    if (!scrollRef.current || !isStreamingRef.current) return;

    try {
      const scrollElement = scrollRef.current;
      const currentHeight = scrollElement.scrollHeight;

      console.log('ChatContentContainer streaming height check:', {
        currentHeight,
        lastHeight: lastContentHeightRef.current,
        heightDiff: currentHeight - lastContentHeightRef.current,
        isStreaming: isStreamingRef.current,
      });

      // Initialize baseline height or check for changes
      if (lastContentHeightRef.current === 0) {
        console.log('ChatContentContainer: Setting initial baseline height:', currentHeight);
        lastContentHeightRef.current = currentHeight;
        return;
      }

      const heightDiff = currentHeight - lastContentHeightRef.current;

      // Lower threshold: any height increase triggers scroll during streaming
      if (heightDiff > 0) {
        console.log('ChatContentContainer: Content height increased by', heightDiff, 'px, scrolling');

        // Check if user has manually scrolled up significantly during streaming
        const { scrollTop, clientHeight } = scrollElement;
        const distanceFromBottom = currentHeight - (scrollTop + clientHeight);

        // If user scrolled up more than 100px, don't force scroll but show a notification
        if (distanceFromBottom > 100) {
          console.log('ChatContentContainer: User scrolled away during streaming, not forcing scroll');
          // Could add a "scroll to bottom" button here
          return;
        }

        // Scroll immediately
        scrollToBottomInstant();

        // Update height tracking
        lastContentHeightRef.current = currentHeight;

        // Reset streaming timeout - keep streaming mode active
        if (streamingTimeoutRef.current) {
          clearTimeout(streamingTimeoutRef.current);
          streamingTimeoutRef.current = null;
        }

        streamingTimeoutRef.current = setTimeout(() => {
          console.log('ChatContentContainer: Exiting streaming mode after content timeout');
          isStreamingRef.current = false;

          // Clean up MutationObserver when exiting streaming mode
          if (mutationObserverRef.current) {
            mutationObserverRef.current.disconnect();
            mutationObserverRef.current = null;
            console.log('ChatContentContainer: MutationObserver stopped on timeout');
          }
        }, 10000);
      }
    } catch (error) {
      console.error('ChatContentContainer: Error in checkContentHeight:', error);
    }
  }, [scrollToBottomInstant]);

  // Force scroll check regardless of height changes
  const forceScrollCheck = useCallback(() => {
    if (!scrollRef.current || !isStreamingRef.current) return;

    try {
      const scrollElement = scrollRef.current;
      const { scrollTop, scrollHeight, clientHeight } = scrollElement;
      const isAtBottom = scrollTop + clientHeight >= scrollHeight - 5;

      console.log('ChatContentContainer force scroll check:', {
        scrollTop,
        scrollHeight,
        clientHeight,
        isAtBottom,
        distanceFromBottom: scrollHeight - (scrollTop + clientHeight),
      });

      // If not at bottom during streaming, scroll to bottom
      if (!isAtBottom) {
        const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);

        // Only respect user scrolling if they scrolled significantly up
        if (distanceFromBottom <= 100) {
          console.log('ChatContentContainer: Forcing scroll to bottom during streaming');
          scrollToBottomInstant();
        }
      }

      // Update height tracking
      lastContentHeightRef.current = scrollElement.scrollHeight;

      // Reset streaming timeout
      if (streamingTimeoutRef.current) {
        clearTimeout(streamingTimeoutRef.current);
        streamingTimeoutRef.current = null;
      }

      streamingTimeoutRef.current = setTimeout(() => {
        console.log('ChatContentContainer: Exiting streaming mode after content timeout');
        isStreamingRef.current = false;

        // Clean up MutationObserver when exiting streaming mode
        if (mutationObserverRef.current) {
          mutationObserverRef.current.disconnect();
          mutationObserverRef.current = null;
          console.log('ChatContentContainer: MutationObserver stopped on timeout');
        }
      }, 10000);
    } catch (error) {
      console.error('ChatContentContainer: Error in forceScrollCheck:', error);
    }
  }, [scrollToBottomInstant]);

  // Clean up streaming mode
  const cleanupStreamingMode = useCallback(() => {
    console.log('ChatContentContainer: Cleaning up streaming mode');

    isStreamingRef.current = false;

    if (streamingTimeoutRef.current) {
      clearTimeout(streamingTimeoutRef.current);
      streamingTimeoutRef.current = null;
    }

    if (backupIntervalRef.current) {
      clearInterval(backupIntervalRef.current);
      backupIntervalRef.current = null;
      console.log('ChatContentContainer: Backup interval cleared');
    }

    if (mutationObserverRef.current) {
      try {
        mutationObserverRef.current.disconnect();
        mutationObserverRef.current = null;
        console.log('ChatContentContainer: MutationObserver cleaned up');
      } catch (error) {
        console.error('ChatContentContainer: Error disconnecting MutationObserver:', error);
      }
    }
  }, []);

  // Start streaming mode for new messages
  const startStreamingMode = useCallback(() => {
    console.log('ChatContentContainer: Starting streaming mode');

    // Clean up any existing streaming mode first
    cleanupStreamingMode();

    // Enter streaming mode - disable user scroll detection
    isStreamingRef.current = true;
    isUserScrollingRef.current = false;

    // Scroll to bottom immediately
    scrollToBottomInstant();

    // Reset height tracking
    lastContentHeightRef.current = 0;

    // Set up MutationObserver to watch for DOM changes
    if (scrollRef.current) {
      try {
        mutationObserverRef.current = new MutationObserver(mutations => {
          // Only process if we're still in streaming mode
          if (!isStreamingRef.current) return;

          console.log('ChatContentContainer: MutationObserver detected changes:', mutations.length);

          // Always trigger scroll check for any mutation during streaming
          // Use both height-based and force-based checks
          setTimeout(() => {
            checkContentHeight();
            forceScrollCheck();
          }, 5); // Very short delay to let DOM settle
        });

        // Monitor all possible DOM changes that could affect content
        mutationObserverRef.current.observe(scrollRef.current, {
          childList: true, // Child elements added/removed
          subtree: true, // Monitor entire subtree
          characterData: true, // Text content changes
          attributes: true, // All attribute changes
          attributeOldValue: true, // Track attribute value changes
          characterDataOldValue: true, // Track text changes
        });

        console.log('ChatContentContainer: Enhanced MutationObserver started');
      } catch (error) {
        console.error('ChatContentContainer: Error creating MutationObserver:', error);
      }
    }

    // Also set up a backup interval to ensure scrolling continues
    backupIntervalRef.current = setInterval(() => {
      if (!isStreamingRef.current) {
        if (backupIntervalRef.current) {
          clearInterval(backupIntervalRef.current);
          backupIntervalRef.current = null;
        }
        return;
      }

      console.log('ChatContentContainer: Backup scroll check');
      forceScrollCheck();
    }, 500); // Check every 500ms as backup

    // Exit streaming mode after no content updates for 10 seconds
    streamingTimeoutRef.current = setTimeout(() => {
      console.log('ChatContentContainer: Exiting streaming mode after timeout');
      cleanupStreamingMode();
    }, 10000);
  }, [scrollToBottomInstant, checkContentHeight, forceScrollCheck, cleanupStreamingMode]);

  // Monitor history changes for new messages
  useEffect(() => {
    if (!scrollRef.current) return;

    const currentMessageCount = history.length;
    const isNewMessage = currentMessageCount > prevMessageCountRef.current;

    console.log('ChatContentContainer message count check:', {
      currentMessageCount,
      prevCount: prevMessageCountRef.current,
      isNewMessage,
      isStreaming: isStreamingRef.current,
    });

    // Handle new messages - always scroll to bottom and start streaming mode
    if (isNewMessage) {
      console.log('ChatContentContainer: New message detected, starting streaming mode');

      prevMessageCountRef.current = currentMessageCount;
      startStreamingMode();
    } else if (!isStreamingRef.current) {
      // Handle content updates when not in streaming mode (e.g., static content changes)
      const scrollElement = scrollRef.current;
      if (scrollElement && !isUserScrollingRef.current) {
        const currentHeight = scrollElement.scrollHeight;
        const heightDiff = currentHeight - lastContentHeightRef.current;

        if (heightDiff > 0) {
          console.log('ChatContentContainer: Non-streaming content change, scrolling');
          scrollToBottomInstant();
          lastContentHeightRef.current = currentHeight;
        }
      }
    }
  }, [history.length, startStreamingMode, scrollToBottomInstant]);

  // Add scroll event listener and cleanup
  useEffect(() => {
    const scrollElement = scrollRef.current;
    if (scrollElement) {
      scrollElement.addEventListener('scroll', handleScrollEvent);
      return () => {
        scrollElement.removeEventListener('scroll', handleScrollEvent);
        // Use the centralized cleanup function
        cleanupStreamingMode();
      };
    }
  }, [handleScrollEvent, cleanupStreamingMode]);

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
      <div ref={scrollRef} className='h-full w-full mx-auto overflow-y-auto' style={{ scrollBehavior: 'smooth' }}>
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
