import React from 'react';
import FinancialAnalysisPage from './FinancialAnalysisPage';
import { supportedFinancialProtocol } from './report-data';

/** Shared authenticated/offline workspace entry, with explicit protocol dispatch. */
const FinancialReportView: React.FC<React.ComponentProps<typeof FinancialAnalysisPage>> = props => {
  if (!supportedFinancialProtocol(props.data)) return <p role='alert'>此报告版本暂不支持，请更新应用后查看。</p>;
  return <FinancialAnalysisPage {...props} />;
};
export default FinancialReportView;
