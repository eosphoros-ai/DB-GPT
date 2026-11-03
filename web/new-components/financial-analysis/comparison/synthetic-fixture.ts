import type { ComparisonReportData } from '../types';

/** SYNTHETIC fixture for development/tests only; never a live-data fallback. */
export function syntheticComparison(): ComparisonReportData {
  const snapshot: ComparisonReportData = {
    schemaVersion: 2,
    mode: 'comparison',
    revision: '12345678-1234-4234-8234-123456789012-synthetic',
    comparison: {
      kind: 'peer',
      title: '合成甲与合成乙 · 横向对比',
      entities: [
        { id: 'entity-a', name: '合成甲公司', identityStatus: 'resolved', identifications: [] },
        { id: 'entity-b', name: '合成乙公司', identityStatus: 'resolved', identifications: [] },
      ],
      periods: ['2024'],
      objects: [
        { entityId: 'entity-a', period: '2024' },
        { entityId: 'entity-b', period: '2024' },
      ],
      baselineEntityId: 'entity-a',
      baselinePeriod: '2024',
      policyVersion: 'paired-disclosure-v1',
      formulaVersion: 'decimal-v1',
      config: { kind: 'peer', baseline_file_id: 'a' },
      cells: [],
      clarifications: [],
      ready: true,
      limitations: ['合成 fixture，非真实年报。'],
    },
    report: {
      id: 'report-synthetic',
      title: '合成对比',
      fiscalPeriod: '2024',
      statementScope: '合并报表',
      currency: '人民币',
      sourceDocumentIds: ['doc-a', 'doc-b'],
      run: {
        id: '12345678-1234-4234-8234-123456789012',
        agentName: '财报对比',
        modelName: 'synthetic',
        skillName: 'financial-report-analyzer',
        status: 'completed',
        evidenceCoverage: 0,
      },
    },
    lifecycle: { dataStatus: 'ready', analysisStatus: 'pending', publicationStatus: 'draft', stage: 'data_ready' },
    documents: [],
    evidence: [],
    facts: [],
    calculations: [],
    findings: [],
    metrics: [],
    members: [],
    steps: [],
    sections: {
      overview: { findingIds: [] },
      profitability: { findingIds: [] },
      cashflow: { findingIds: [] },
      balance: { findingIds: [] },
    },
    artifacts: [],
    agent: { userQuery: '合成比较', summary: '数据已保存，等待分析。', groups: [] },
  };
  for (const [suffix, value] of [
    ['a', '100'],
    ['b', '150'],
  ] as const) {
    const factId = `fact-${suffix}`;
    snapshot.documents.push({
      id: `doc-${suffix}`,
      fileId: suffix,
      entityId: `entity-${suffix}`,
      fileName: `synthetic-${suffix}.pdf`,
      fiscalPeriod: '2024',
      version: '合成文件',
      reportType: '年度报告',
    });
    snapshot.evidence.push({
      id: `ev-${suffix}`,
      label: `E-${suffix}`,
      sourceDocumentId: `doc-${suffix}`,
      page: 2,
      snippet: `SYNTHETIC 营业收入 ${value}`,
      qualityStatus: 'warning',
    });
    snapshot.facts.push({
      id: factId,
      entityId: `entity-${suffix}`,
      sourceDocumentId: `doc-${suffix}`,
      metricCode: 'revenue',
      metricName: '营业收入',
      normalizedValue: value,
      rawValue: value,
      displayValue: `${value}.00 元`,
      unit: '元',
      fiscalPeriod: '2024',
      statementScope: '合并',
      evidenceExcerptIds: [`ev-${suffix}`],
      qualityStatus: 'warning',
    });
    snapshot.comparison.cells.push({
      id: `cell-${suffix}`,
      entityId: `entity-${suffix}`,
      period: '2024',
      metricCode: 'revenue',
      metricName: '营业收入',
      dataStatus: 'available',
      factId,
      calculationId: null,
      candidateFactIds: [factId],
      selectionReason: 'equal_disclosures',
      policyVersion: 'paired-disclosure-v1',
      comparability: { status: 'comparable', rules: ['scope'], reasons: [] },
    });
    snapshot.members.push({
      file_id: suffix,
      file_name: `synthetic-${suffix}.pdf`,
      status: 'completed',
      error: null,
      sha256: suffix.repeat(64),
      extractor_version: 'financial-document-v2',
    });
  }
  snapshot.calculations.push({
    id: 'calc-difference',
    metricCode: 'revenue',
    name: '营业收入差额',
    kind: 'deterministic',
    formula: '对象 - 基准',
    inputFactIds: ['fact-a', 'fact-b'],
    steps: ['150 - 100 = 50 元'],
    result: '50',
    displayResult: '50.00 元',
    unit: '元',
    status: 'calculated',
    comparisonType: 'difference',
    subjectEntityId: 'entity-b',
    baselineEntityId: 'entity-a',
    subjectPeriod: '2024',
    baselinePeriod: '2024',
    direction: 'higher',
  });
  return snapshot;
}
