import React, { useState } from 'react';
import styles from '../financial-analysis.module.css';
import { financialText, useFinancialLocale } from '../i18n';
import type { ComparisonAccess, ComparisonReportData } from '../types';
import { comparisonReason } from './comparison-data';

const ComparisonHeader: React.FC<{ data: ComparisonReportData; access?: ComparisonAccess }> = ({ data, access }) => {
  useFinancialLocale();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [resolutions, setResolutions] = useState<Record<string, { company_name: string; report_year: string }>>({});
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : financialText('financial.request_failed'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={styles.comparisonHeader}>
      <div className={styles.meta}>
        {data.comparison.kind === 'peer'
          ? financialText('financial.compare_companies_in_the_same_year')
          : financialText('financial.compare_years_for_one_company')}{' '}
        · {data.comparison.periods.join(' / ')}
        {' · '}
        {data.report.statementScope} · {data.report.currency}
      </div>
      <div className={styles.comparisonControls}>
        <label>
          {financialText('financial.comparison_baseline')}{' '}
          <select
            aria-label={financialText('financial.comparison_baseline')}
            disabled={!access || busy}
            value={data.comparison.config.baseline_file_id || ''}
            onChange={event => {
              const fileId = event.target.value;
              void run(() => access!.configure({ ...data.comparison.config, baseline_file_id: fileId }, data.revision));
            }}
          >
            <option value='' disabled>
              {financialText('financial.select_comparison_baseline')}
            </option>
            {data.documents
              .filter(document => document.fileId)
              .map(document => (
                <option key={document.id} value={document.fileId}>
                  {data.comparison.entities.find(entity => entity.id === document.entityId)?.name} ·{' '}
                  {document.fiscalPeriod}
                </option>
              ))}
          </select>
        </label>
        {access && data.members.some(member => ['failed', 'interrupted'].includes(member.status)) && (
          <button
            type='button'
            className={styles.textLink}
            disabled={busy}
            onClick={() => void run(() => access.resume(data.revision))}
          >
            {financialText('financial.retry_incomplete_files')}
          </button>
        )}
      </div>
      {!data.comparison.ready && (
        <p className={styles.comparisonGap}>
          {financialText('financial.extractable_data_has_been_saved_but_subjects_or_periods_do_not_yet_s')}
        </p>
      )}
      {data.comparison.clarifications.map((clarification, index) => (
        <div key={clarification.fileId || index} className={styles.comparisonClarification}>
          {clarification.reason ? (
            <p>{comparisonReason(clarification.reason)}</p>
          ) : (
            <>
              <p>
                {financialText('financial.confirm_company_and_reporting_year', {
                  fileName: data.members.find(member => member.file_id === clarification.fileId)?.file_name,
                })}
              </p>
              {access &&
                clarification.fileId &&
                (() => {
                  const fileId = clarification.fileId;
                  const value = resolutions[fileId] || {
                    company_name: clarification.name || '',
                    report_year: clarification.period || '',
                  };
                  return (
                    <div className={styles.comparisonControls}>
                      <input
                        aria-label={financialText('financial.confirm_company_name')}
                        placeholder={financialText('financial.full_company_name_in_the_source')}
                        maxLength={120}
                        value={value.company_name}
                        onChange={event =>
                          setResolutions(current => ({
                            ...current,
                            [fileId]: { ...value, company_name: event.target.value },
                          }))
                        }
                      />
                      <input
                        aria-label={financialText('financial.confirm_reporting_year')}
                        placeholder={financialText('financial.year')}
                        pattern='20[0-9]{2}'
                        maxLength={4}
                        value={value.report_year}
                        onChange={event =>
                          setResolutions(current => ({
                            ...current,
                            [fileId]: { ...value, report_year: event.target.value },
                          }))
                        }
                      />
                      <button
                        type='button'
                        disabled={busy || value.company_name.length < 2 || !/^20\d{2}$/.test(value.report_year)}
                        onClick={() => void run(() => access.resume(data.revision, { [fileId]: value }))}
                      >
                        {financialText('financial.confirm_and_continue')}
                      </button>
                    </div>
                  );
                })()}
            </>
          )}
        </div>
      ))}
      {data.members
        .filter(member => member.status === 'failed' || member.status === 'interrupted')
        .map(member => (
          <p className={styles.comparisonGap} key={member.file_id}>
            {member.file_name}：{member.error || financialText('financial.extraction_incomplete')}
            {financialText('financial.other_valid_data_is_retained')}
          </p>
        ))}
      <p className={styles.meta}>
        {financialText('financial.unit_normalization_does_not_convert_currencies_metric_differences_do')}
      </p>
      {error && <p role='alert'>{error}</p>}
    </div>
  );
};
export default ComparisonHeader;
