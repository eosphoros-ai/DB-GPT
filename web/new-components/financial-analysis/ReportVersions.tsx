import React, { useEffect, useState } from 'react';
import styles from './financial-analysis.module.css';
import type { ReportRevision, ReportRevisionAccess } from './types';

const ReportVersions: React.FC<{ access?: ReportRevisionAccess; revision: string }> = ({ access, revision }) => {
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
        if (!controller.signal.aborted) setError('历史版本暂不可用');
      });
    return () => controller.abort();
  }, [access, revision]);
  if (!access) return null;
  return (
    <label className={styles.meta}>
      报告版本{' '}
      <select
        aria-label='报告版本'
        value={access.selectedRevision || ''}
        onChange={event => access.select(event.target.value || undefined)}
      >
        <option value=''>当前任务</option>
        {versions.map(item => (
          <option key={item.revision} value={item.revision}>
            {item.publicationStatus === 'published' ? '报告已生成' : '数据快照'} · {item.createdAt}
          </option>
        ))}
      </select>
      {error && <span role='status'> {error}</span>}
    </label>
  );
};
export default ReportVersions;
