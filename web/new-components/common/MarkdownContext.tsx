import markdownComponents, { markdownPlugins, preprocessLaTeX } from '@/components/chat/chat-content/config';
import { GPTVis } from '@antv/gpt-vis';
import React from 'react';

const MarkDownContext: React.FC<{
  children: string;
  components?: Parameters<typeof GPTVis>[0]['components'];
}> = ({ children, components }) => {
  return (
    <GPTVis components={{ ...markdownComponents, ...components }} {...markdownPlugins}>
      {preprocessLaTeX(children)}
    </GPTVis>
  );
};

export default MarkDownContext;
