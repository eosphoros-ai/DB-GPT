import markdownComponents from '@/components/chat/chat-content/config';
import React from 'react';
import { GPTVis } from '@antv/gpt-vis';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';

const MarkDownContext: React.FC<{ children: string }> = ({ children }) => {
  return (
    <GPTVis
      components={{ ...markdownComponents }}
      rehypePlugins={[rehypeRaw]}
      remarkPlugins={[remarkGfm]}
    >
      {children}
    </GPTVis>
  );
};

export default MarkDownContext;
