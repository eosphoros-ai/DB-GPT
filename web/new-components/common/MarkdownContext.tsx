import markdownComponents, { markdownPlugins, preprocessLaTeX } from '@/components/chat/chat-content/config';
import { GPTVis } from '@antv/gpt-vis';
import React from 'react';

const MarkDownContext: React.FC<{ children: string }> = ({ children }) => {
  return (
    <GPTVis components={{ ...markdownComponents }} {...markdownPlugins}>
      {preprocessLaTeX(children)}
    </GPTVis>
  );
};

export default MarkDownContext;
