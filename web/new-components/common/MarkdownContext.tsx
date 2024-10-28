import markdownComponents from '@/components/chat/chat-content/config';
import { GPTVis } from '@antv/gpt-vis';
import React from 'react';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';

const MarkDownContext: React.FC<{ children: string }> = ({ children }) => {
  return (
    <GPTVis components={{ ...markdownComponents }} rehypePlugins={[rehypeRaw]} remarkPlugins={[remarkGfm]}>
      {children}
    </GPTVis>
  );
};

export default MarkDownContext;
