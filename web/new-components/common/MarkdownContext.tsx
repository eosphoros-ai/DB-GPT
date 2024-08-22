import markdownComponents from '@/components/chat/chat-content/config';
import React from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';

const MarkDownContext: React.FC<{ children: string }> = ({ children }) => {
  return (
    <ReactMarkdown components={{ ...markdownComponents }} rehypePlugins={[rehypeRaw]} remarkPlugins={[remarkGfm]}>
      {children}
    </ReactMarkdown>
  );
};

export default MarkDownContext;
