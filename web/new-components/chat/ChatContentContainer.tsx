import ChatHeader from '@/new-components/chat/header/ChatHeader';
import dynamic from 'next/dynamic';
import React, { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';

const ChatCompletion = dynamic(() => import('@/new-components/chat/content/ChatCompletion'), { ssr: false });

const ChatContentContainer = ({}, ref: React.ForwardedRef<any>) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [isScrollToTop, setIsScrollToTop] = useState<boolean>(false);

  useImperativeHandle(ref, () => {
    return scrollRef.current;
  });

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.addEventListener('scroll', () => {
        const st = scrollRef.current?.scrollTop || 0;
        if (st >= 42 + 32) {
          setIsScrollToTop(true);
        } else {
          setIsScrollToTop(false);
        }
      });
    }
    return () => {
      // eslint-disable-next-line react-hooks/exhaustive-deps
      scrollRef.current && scrollRef.current.removeEventListener('scroll', () => {});
    };
  }, []);

  return (
    <div className="flex flex-1 overflow-hidden">
      <div ref={scrollRef} className="h-full w-full mx-auto overflow-y-auto">
        <ChatHeader isScrollToTop={isScrollToTop} />
        <ChatCompletion />
      </div>
    </div>
  );
};

export default forwardRef(ChatContentContainer);
