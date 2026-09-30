export type SupportStatus = 'supported' | 'partial' | 'unresolved';

export type QualityStatus = 'verified' | 'reviewed' | 'warning';

export type InformationKind = 'fact' | 'calculation' | 'analysis';

export interface AnalysisRun {
  id: string;
  agentName: string;
  modelName: string;
  skillName: 'financial-report-analyzer';
  status: 'pending' | 'running' | 'completed' | 'failed';
  evidenceCoverage: number;
  completedAt?: string;
  startedAt?: string;
}

export interface FinancialReport {
  id: string;
  companyName: string;
  shortName: string;
  stockCode: string;
  title: string;
  fiscalPeriod: string;
  statementScope: string;
  currency: string;
  sourceDocumentIds: string[];
  run: AnalysisRun;
}

export interface SourceDocument {
  id: string;
  fileName: string;
  reportType: string;
  fiscalPeriod: string;
  version: string;
  sizeBytes?: number;
  fileId?: string;
  pageCount?: number;
}

export interface EvidenceExcerpt {
  id: string;
  sourceDocumentId: string;
  page: number;
  section?: string;
  table?: string;
  row?: string;
  column?: string;
  snippet: string;
  extractedValue?: string;
  qualityStatus: QualityStatus;
  headerPage?: number;
  headerSnippet?: string;
  unitPage?: number;
  unitText?: string;
}

export interface SourcePreviewAccess {
  loadPage: (documentId: string, page: number, signal: AbortSignal) => Promise<Blob>;
  download: (document: SourceDocument) => Promise<void>;
}

export interface FinancialExport {
  id: string;
  run_id: string;
  revision: string;
  format: 'json' | 'html';
  file_name: string;
  size_bytes: number;
  created_at: string;
  sha256: string;
}

export interface ReportExportAccess {
  list: (signal: AbortSignal) => Promise<FinancialExport[]>;
  create: (format: 'json' | 'html', revision: string) => Promise<FinancialExport>;
  download: (file: FinancialExport) => Promise<void>;
}

export interface FinancialFact {
  id: string;
  metricCode: string;
  metricName: string;
  rawValue: string;
  normalizedValue: number | string | null;
  displayValue: string;
  unit: string;
  fiscalPeriod: string;
  statementScope: string;
  evidenceExcerptIds: string[];
  qualityStatus: QualityStatus;
}

export interface CalculationTrace {
  id: string;
  name: string;
  kind: 'deterministic';
  formula: string;
  inputFactIds: string[];
  steps: string[];
  result: number | string | null;
  displayResult: string;
  unit: string;
}

export interface InlineTraceNode {
  kind: 'fact' | 'calculation' | 'evidence';
  refId: string;
  label?: string;
  displayValue?: string;
}

export interface AnalysisFinding {
  id: string;
  section: string;
  title: string;
  summary: string;
  supportStatus: SupportStatus;
  factIds: string[];
  calculationIds: string[];
  evidenceExcerptIds: string[];
  inlineTrace: InlineTraceNode[];
  counterEvidence?: string[];
  unresolvedQuestions?: string[];
}

export interface FinancialMetric {
  id: string;
  code: string;
  name: string;
  displayValue: string;
  change?: number;
  changeDisplay?: string;
  changeLabel?: string;
  changeUnit?: '%' | 'pp' | 'x';
  informationKind: Exclude<InformationKind, 'analysis'>;
  factIds?: string[];
  calculationId?: string;
  findingId?: string;
  citationLabel: string;
}

export interface AgentExecutionStep {
  startedAt?: string;
  completedAt?: string;
  elapsedMs?: number;
  id: string;
  order: number;
  type: 'skill' | 'read' | 'python' | 'analysis' | 'html';
  title: string;
  tool?: string;
  script?: string;
  detail: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  capability: 'existing' | 'mock-extension';
}

export interface TrendPoint {
  year: string;
  metric: string;
  value: number;
}

export interface MockAnswer {
  question: string;
  answer: string;
  findingId: string;
}

export interface EvidenceSelection {
  findingId?: string;
  metricId?: string;
  factId?: string;
  calculationId?: string;
  evidenceId?: string;
}

export type OpenEvidence = (selection: EvidenceSelection) => void;

export interface ReportQuestionAnswer {
  runId: string;
  revision: string;
  question: string;
  answer: string;
  modelName: string;
  factIds: string[];
  calculationIds: string[];
  evidenceExcerptIds: string[];
  citations: Array<Pick<EvidenceSelection, 'factId' | 'calculationId'>>;
  insufficientEvidence: boolean;
  answerMode: 'validated' | 'references_only' | 'insufficient';
  supportStatus: 'partial' | 'unresolved';
}

export interface ReportQuestionAccess {
  ask: (question: string, revision: string, signal: AbortSignal) => Promise<ReportQuestionAnswer>;
}

export interface ReportSectionData {
  title?: string;
  description?: string;
  findingIds: string[];
  factIds?: string[];
  calculationIds?: string[];
  evidenceIds?: string[];
  comparisonLabel?: string;
  rateComparisons?: Array<{
    id: string;
    name: string;
    currentCalculationId: string;
    previousCalculationId: string;
    changeCalculationId: string;
  }>;
}

export interface ReportArtifact {
  id: string;
  name: string;
  kind: 'html' | 'png' | 'json';
  detail: string;
  sizeBytes?: number;
}

/** A complete snapshot. Missing arrays/values must never resolve to demo data. */
export interface ReportData {
  workflow?: {
    dataQuality?: { availableFacts: number; missingFacts: string[]; unavailableCalculations: Array<{ id: string; name: string; reason: string }> };
    version: number;
    status: 'draft' | 'published';
    publishedAt: string | null;
    review: {
      at: string;
      kind: 'agent-review';
      items: Array<{ topic_id: string; verdict: string; note: string }>;
    } | null;
    topics: Array<{
      id: string;
      title: string;
      section: 'overview' | 'profitability' | 'cashflow' | 'balance';
      status: 'pending' | 'running' | 'ready' | 'reviewed' | 'insufficient' | 'failed' | 'needs_revision';
      attempts: number;
      failures: number;
      findingIds: string[];
      note: string;
      review?: { verdict: string; note: string };
      history: unknown[];
    }>;
    history: Array<{ revision: string; publishedAt: string }>;
  };
  schemaVersion: 1;
  revision: string;
  mode: 'demo' | 'report';
  analysis?: {
    status: 'running' | 'completed' | 'partial' | 'failed';
    modelName: string;
    startedAt: string;
    completedAt?: string | null;
    error?: string | null;
    rejectedCount: number;
  };
  report: FinancialReport;
  documents: SourceDocument[];
  evidence: EvidenceExcerpt[];
  facts: FinancialFact[];
  calculations: CalculationTrace[];
  findings: AnalysisFinding[];
  metrics: FinancialMetric[];
  trends: {
    revenue: TrendPoint[];
    cashFlow: TrendPoint[];
    profit: TrendPoint[];
    expenses: Array<{ expense: string; year: string; value: number; calculationId?: string }>;
    financialUnit: string;
    profitUnit: string;
  };
  steps: AgentExecutionStep[];
  sections: Record<'overview' | 'profitability' | 'cashflow' | 'balance', ReportSectionData>;
  healthMetrics: Array<{ id: string; name: string; displayValue: string | null; selection?: EvidenceSelection }>;
  statements: {
    unit: string;
    periods: Array<{ period: string; label: string }>;
    rows: Array<{ id: string; name: string; factIds: string[] }>;
  };
  artifacts: ReportArtifact[];
  agent: {
    userQuery: string;
    summary: string;
    groups: Array<{ id: string; title: string; content: string; stepIds: string[] }>;
  };
  /** Canned answers belong exclusively to the demo. */
  demoQuestions?: Array<MockAnswer & { label: string; keywords: string[]; priority: number }>;
}
