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
  entityId?: string;
  sha256?: string;
  extractorVersion?: string;
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
  label?: string;
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
  entityId?: string;
  sourceDocumentId?: string;
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
  entityId?: string;
  metricCode?: string;
  subjectEntityId?: string;
  baselineEntityId?: string;
  subjectPeriod?: string;
  baselinePeriod?: string;
  comparisonType?: 'difference' | 'growth';
  direction?: 'higher' | 'lower' | 'equal' | 'unavailable';
  status?: 'calculated' | 'unavailable';
  reason?: string | null;
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
  entityIds?: string[];
  periods?: string[];
  metricCodes?: string[];
  subjectEntityId?: string;
  baselineEntityId?: string | null;
  comparisonDirection?: 'higher' | 'lower' | 'equal' | 'none';
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
  capability: 'existing';
}

export interface TrendPoint {
  year: string;
  metric: string;
  value: number;
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

/** A complete snapshot of a saved report. */
export interface ReportData {
  workflow?: {
    dataQuality?: {
      availableFacts: number;
      missingFacts: string[];
      unavailableCalculations: Array<{ id: string; name: string; reason: string }>;
    };
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
      saveAttempts?: number;
      validationHistory?: Array<{
        at: string;
        revision: string;
        errorCode: string;
        issues: Array<{ finding_index?: number; field?: string; code: string }>;
      }>;
      errorCode?: string | null;
      issues?: Array<{
        finding_index?: number;
        field?: string;
        code: string;
        invalid_tokens?: string[];
        missing_metrics?: string[];
        hint?: string;
      }>;
      findingIds: string[];
      note: string;
      review?: { verdict: string; note: string };
      history: unknown[];
    }>;
    history: Array<{ revision: string; publishedAt: string }>;
  };
  schemaVersion: 1;
  revision: string;
  mode: 'report';
  analysis?: {
    status: 'running' | 'completed' | 'partial' | 'failed';
    modelName: string;
    startedAt: string;
    completedAt?: string | null;
    error?: string | null;
    rejectedCount: number;
    reviewIssues?: string[];
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
}

export interface ComparisonConfig {
  kind: 'peer' | 'trend';
  baseline_file_id?: string | null;
  policy_version?: 'paired-disclosure-v1';
  formula_version?: 'decimal-v1';
}

export interface ComparisonEntity {
  id: string;
  name: string;
  identityStatus: 'resolved' | 'ambiguous';
  identifications: Array<{
    fileId: string;
    name: string | null;
    period: string | null;
    status: 'resolved' | 'ambiguous';
    candidates: string[];
    basis: string;
  }>;
}

export interface ComparisonCell {
  id: string;
  entityId: string;
  period: string;
  metricCode: string;
  metricName: string;
  dataStatus: 'available' | 'missing' | 'conflict' | 'extraction_failed';
  factId: string | null;
  calculationId: string | null;
  candidateFactIds: string[];
  selectionReason: string;
  policyVersion: string;
  comparability: {
    status: 'unchecked' | 'comparable' | 'incomparable';
    rules: string[];
    reasons: string[];
  };
}

export interface ComparisonMember {
  file_id: string;
  file_name: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'interrupted';
  error: string | null;
  sha256: string;
  extractor_version: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface ComparisonReportData
  extends Omit<ReportData, 'schemaVersion' | 'mode' | 'report' | 'trends' | 'healthMetrics' | 'statements'> {
  schemaVersion: 2;
  mode: 'comparison';
  report: Omit<FinancialReport, 'companyName' | 'shortName' | 'stockCode'>;
  comparison: {
    kind: 'peer' | 'trend';
    title: string;
    entities: ComparisonEntity[];
    periods: string[];
    objects: Array<{ entityId: string; period: string }>;
    baselineEntityId: string | null;
    baselinePeriod: string | null;
    policyVersion: string;
    formulaVersion: string;
    config: ComparisonConfig;
    cells: ComparisonCell[];
    clarifications: Array<{
      reason?: string;
      fileId?: string;
      name?: string | null;
      period?: string | null;
      candidates?: string[];
    }>;
    ready: boolean;
    limitations: string[];
  };
  lifecycle: {
    dataStatus: 'ready' | 'incomplete';
    analysisStatus: 'pending' | 'running' | 'completed' | 'partial' | 'failed';
    publicationStatus: 'draft' | 'published';
    stage: string;
  };
  members: ComparisonMember[];
}

export type FinancialReportData = ReportData | ComparisonReportData;

export interface ReportRevision {
  revision: string;
  createdAt: string;
  publicationStatus: string;
  sha256: string;
}

export interface ReportRevisionAccess {
  selectedRevision?: string;
  list: (signal: AbortSignal) => Promise<ReportRevision[]>;
  select: (revision?: string) => void;
}

export interface ComparisonAccess {
  configure: (config: ComparisonConfig, revision: string) => Promise<void>;
  resume: (
    revision: string,
    resolutions?: Record<string, { company_name: string; report_year: string }>,
  ) => Promise<void>;
}
