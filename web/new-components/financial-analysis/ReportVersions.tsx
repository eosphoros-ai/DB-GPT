import React, { useEffect, useState } from 'react';
import styles from './financial-analysis.module.css';
import { financialText, useFinancialLocale } from './i18n';
import type { ReportRevision, ReportRevisionAccess } from './types';

const ReportVersions: React.FC<{ access?: ReportRevisionAccess; revision: string }> = ({ access, revision }) => {
  useFinancialLocale();
  const [versions, setVersions] = useState<ReportRevision[]>([]);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!access) return;
    const controller = new AbortController();
    void access
      .list(controller.signal)
      .then(items => {
        if (!controller.signal.aborted) setVersions(items);
      })
      .catch(() => {
        if (!controller.signal.aborted) setError(financialText('financial.report_history_is_unavailable'));
      });
    return () => controller.abort();
  }, [access, revision]);
  if (!access) return null;
  return (
    <label className={styles.meta}>
      {financialText('financial.report_version')}{' '}
      <select
        aria-label={financialText('financial.report_version')}
        value={access.selectedRevision || ''}
        onChange={event => access.select(event.target.value || undefined)}
      >
        <option value=''>{financialText('financial.current_task')}</option>
        {versions.map(item => (
          <option key={item.revision} value={item.revision}>
            {item.publicationStatus === 'published'
              ? financialText('financial.report_generated')
              : financialText('financial.data_snapshot')}{' '}
            · {item.createdAt}
          </option>
        ))}
      </select>
      {error && <span role='status'> {error}</span>}
    </label>
  );
};
export default ReportVersions;
