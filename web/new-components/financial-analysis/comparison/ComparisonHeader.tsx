import React, { useState } from 'react';
import styles from '../financial-analysis.module.css';
import type { ComparisonAccess, ComparisonReportData } from '../types';
import { comparisonReason } from './comparison-data';

const ComparisonHeader: React.FC<{ data: ComparisonReportData; access?: ComparisonAccess }> = ({ data, access }) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [resolutions, setResolutions] = useState<Record<string, { company_name: string; report_year: string }>>({});
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await action();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '请求失败');
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className={styles.comparisonHeader}>
      <div className={styles.meta}>
        {data.comparison.kind === 'peer' ? '同年度多公司对比' : '同公司跨年对比'} ·{' '}
        {data.comparison.periods.join(' / ')}
        {' · '}
        {data.report.statementScope} · {data.report.currency}
      </div>
      <div className={styles.comparisonControls}>
        <label>
          比较基准{' '}
          <select
            aria-label='比较基准'
            disabled={!access || busy}
            value={data.comparison.config.baseline_file_id || ''}
            onChange={event => {
              const fileId = event.target.value;
              void run(() => access!.configure({ ...data.comparison.config, baseline_file_id: fileId }, data.revision));
            }}
          >
            {data.documents.map(document => (
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
            重试未完成文件
          </button>
        )}
      </div>
      {!data.comparison.ready && (
        <p className={styles.comparisonGap}>当前已保存可提取资料，比较对象或期间尚不足以构成有效对比。</p>
      )}
      {data.comparison.clarifications.map((clarification, index) => (
        <div key={clarification.fileId || index} className={styles.comparisonClarification}>
          {clarification.reason ? (
            <p>{comparisonReason(clarification.reason)}</p>
          ) : (
            <>
              <p>
                请确认 {data.members.find(member => member.file_id === clarification.fileId)?.file_name}{' '}
                的公司和报告年度。
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
                        aria-label='确认公司名称'
                        placeholder='原文中的完整公司名称'
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
                        aria-label='确认报告年度'
                        placeholder='年度'
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
                        确认并继续
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
            {member.file_name}：{member.error || '提取未完成'}。其他有效数据已保留。
          </p>
        ))}
      <p className={styles.meta}>单位统一不涉及汇率换算。指标差异不等于企业优劣，解释仍需结合业务结构与附注。</p>
      {error && <p role='alert'>{error}</p>}
    </div>
  );
};
export default ComparisonHeader;
