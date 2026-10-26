import React from 'react';
import FinancialAnalysisPage from './FinancialAnalysisPage';
import { financialText, useFinancialLocale } from './i18n';
import { supportedFinancialProtocol } from './report-data';

/** Shared authenticated/offline workspace entry, with explicit protocol dispatch. */
const FinancialReportView: React.FC<React.ComponentProps<typeof FinancialAnalysisPage>> = props => {
  useFinancialLocale();
  if (!supportedFinancialProtocol(props.data))
    return (
      <p role='alert'>
        {financialText('financial.this_report_version_is_unsupported_update_the_application_to_view_it')}
      </p>
    );
  return <FinancialAnalysisPage {...props} />;
};
export default FinancialReportView;
