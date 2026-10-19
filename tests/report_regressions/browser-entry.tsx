import React from 'react';
import { createRoot } from 'react-dom/client';
import { flushSync } from 'react-dom';
import HtmlReportEvidence from '../../web/new-components/report/HtmlReportEvidence';
import { exportRenderedReportHtml } from '../../web/new-components/report/report-print';

const root = createRoot(document.getElementById('root')!);
(window as any).mountReport = (html: string) => {
  flushSync(() => root.render(<HtmlReportEvidence html={html} reportId='browser-regression' reportRunId='run-1' />));
};
(window as any).exportReport = () => exportRenderedReportHtml(document.querySelector('iframe')!);
(window as any).probeLoaded = true;
