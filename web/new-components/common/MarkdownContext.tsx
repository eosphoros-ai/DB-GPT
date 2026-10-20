import markdownComponents, { markdownPlugins, preprocessLaTeX } from '@/components/chat/chat-content/config';
import FinancialCitationLink from '@/new-components/financial-analysis/FinancialCitationLink';
import { cleanFinancialAnswerText, type FinancialCitation } from '@/new-components/financial-analysis/report-citations';
import { GPTVis } from '@antv/gpt-vis';
import React from 'react';

const DefaultLink = markdownComponents?.a as React.ElementType | undefined;

const MarkDownContext: React.FC<{
  children: string;
  onFinancialCitationClick?: (citation: FinancialCitation) => void;
}> = ({ children, onFinancialCitationClick }) => {
  const content = children.includes('#financial-report/') ? cleanFinancialAnswerText(children) : children;
  return (
    <GPTVis
      components={{
        ...markdownComponents,
        a: props =>
          props.href?.startsWith('#financial-report/') || !DefaultLink ? (
            <FinancialCitationLink {...props} onCitationClick={onFinancialCitationClick} />
          ) : (
            <DefaultLink {...props} />
          ),
      }}
      {...markdownPlugins}
    >
      {preprocessLaTeX(content)}
    </GPTVis>
  );
};

export default MarkDownContext;
