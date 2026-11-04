import React from 'react';
import { financialText, useFinancialLocale } from './i18n';
import { parseFinancialCitation, type FinancialCitation } from './report-citations';

interface FinancialCitationLinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  node?: unknown;
  onCitationClick?: (citation: FinancialCitation) => void;
}

export default function FinancialCitationLink({
  href,
  children,
  node: _node,
  onCitationClick,
  ...props
}: FinancialCitationLinkProps) {
  useFinancialLocale();
  const citation = parseFinancialCitation(href);
  if (citation) {
    return (
      <sup className='ml-0.5 inline-block select-none align-super text-[11px] leading-none'>
        <button
          type='button'
          className='rounded px-0.5 font-normal text-slate-500 transition-colors hover:bg-blue-50 hover:text-blue-600 focus-visible:outline focus-visible:outline-blue-500 dark:text-slate-400 dark:hover:text-blue-400'
          title={props.title || financialText('financial.view_exact_values_and_source_evidence_in_the_report')}
          aria-label={financialText('financial.view_report_reference_value', { value1: String(children) })}
          data-financial-reference={citation.refId}
          data-report-run={citation.runId}
          disabled={!onCitationClick}
          onClick={() => onCitationClick?.(citation)}
        >
          {children}
        </button>
      </sup>
    );
  }
  if (href?.startsWith('#financial-report/')) return <span>{children}</span>;
  return (
    <a href={href} {...props}>
      {children}
    </a>
  );
}
