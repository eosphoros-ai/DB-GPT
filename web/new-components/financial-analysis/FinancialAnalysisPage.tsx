import {
  AppstoreOutlined,
  ArrowLeftOutlined,
  CheckCircleFilled,
  CodeOutlined,
  DesktopOutlined,
  FilePdfOutlined,
  FileSearchOutlined,
  FileTextOutlined,
  FolderOpenOutlined,
  InfoCircleOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { Tooltip } from 'antd';
import { useRouter } from 'next/router';
import React, { useEffect, useRef, useState } from 'react';
import AgentRunPanel from './AgentRunPanel';
import AskDbGPTDock from './AskDbGPTDock';
import EvidencePanel from './EvidencePanel';
import ExecutionProcessPanel, { AnalysisActions } from './ExecutionProcessPanel';
import { ReportDataProvider, useReportData } from './ReportDataContext';
import ReportExports from './ReportExports';
import { BalanceTab, CashFlowTab, OverviewTab, ProfitabilityTab, StatementsTab } from './ReportSections';
import ReportVersions from './ReportVersions';
import SourcePreviewPanel from './SourcePreviewPanel';
import ComparisonHeader from './comparison/ComparisonHeader';
import ComparisonSections from './comparison/ComparisonSections';
import styles from './financial-analysis.module.css';
import { financialText, useFinancialLocale } from './i18n';
import { resolveFinancialCitation, type FinancialCitationTarget } from './report-citations';
import { reportRunState } from './report-data';
import {
  ComparisonAccess,
  EvidenceExcerpt,
  EvidenceSelection,
  FinancialReportData,
  ReportExportAccess,
  ReportQuestionAccess,
  ReportRevisionAccess,
  SourcePreviewAccess,
} from './types';

type WorkspaceTab = 'report' | 'execution' | 'files' | 'skill' | 'evidence';
const workspaceTabs: Array<{ key: WorkspaceTab; label: string; icon: React.ReactNode }> = [
  {
    key: 'report',
    get label() {
      return financialText('financial.report');
    },
    icon: <FileTextOutlined />,
  },
  {
    key: 'execution',
    get label() {
      return financialText('financial.execution');
    },
    icon: <DesktopOutlined />,
  },
  {
    key: 'files',
    get label() {
      return financialText('financial.files');
    },
    icon: <FolderOpenOutlined />,
  },
  { key: 'skill', label: 'financial-report-analyzer', icon: <AppstoreOutlined /> },
  {
    key: 'evidence',
    get label() {
      return financialText('financial.evidence');
    },
    icon: <FileSearchOutlined />,
  },
];
const capabilityNote = () =>
  financialText('financial.this_workspace_shows_the_selected_report_questions_use_that_report_w');

const ArtifactContext: React.FC<{
  comparisonAccess?: ComparisonAccess;
  revisionAccess?: ReportRevisionAccess;
}> = ({ comparisonAccess, revisionAccess }) => {
  useFinancialLocale();
  const { data } = useReportData();
  const { report, documents } = data;
  return (
    <section className={styles.reportContext}>
      <div className={styles.contextByline}>
        Financial Analysis <span>／ {report.run.skillName}</span>
      </div>
      <h1>{data.mode === 'comparison' ? data.comparison.title : data.report.companyName}</h1>
      <div className={styles.meta}>
        {report.title} · {report.statementScope} · {report.currency} ·{' '}
        {documents.map(item => item.fileName).join(' / ') || financialText('financial.source_file_unavailable')}
      </div>
      <ReportVersions access={revisionAccess} revision={data.revision} />
      {data.mode === 'comparison' && <ComparisonHeader data={data} access={comparisonAccess} />}
    </section>
  );
};

const FilesPanel: React.FC<{
  onOpenSource: (evidence: EvidenceExcerpt) => void;
  onOpenArtifact: () => void;
  exportAccess?: ReportExportAccess;
}> = ({ onOpenSource, onOpenArtifact, exportAccess }) => {
  useFinancialLocale();
  const { data } = useReportData();
  const files = [
    ...data.documents.map(document => {
      const evidence = data.evidence.find(item => item.sourceDocumentId === document.id);
      return {
        name: document.fileName,
        detail: financialText('financial.uploaded_file_pdfvalue', {
          value1: document.sizeBytes === undefined ? '' : ` · ${(document.sizeBytes / 1024 / 1024).toFixed(1)} MB`,
        }),
        icon: <FilePdfOutlined />,
        action: evidence ? () => onOpenSource(evidence) : undefined,
      };
    }),
    ...data.artifacts.map(artifact => ({
      name: artifact.name,
      detail: artifact.detail,
      icon: artifact.kind === 'json' ? <CodeOutlined /> : <FileTextOutlined />,
      action: artifact.kind === 'html' ? onOpenArtifact : undefined,
    })),
  ];
  return (
    <div className={styles.utilityPanel}>
      <h2>{financialText('financial.task_files')}</h2>
      <p className={styles.sectionDescription}>
        {financialText('financial.inputs_and_analysis_outputs_for_this_task')}
      </p>
      {exportAccess && <ReportExports access={exportAccess} />}
      {!files.length && <p className={styles.meta}>{financialText('financial.no_files')}</p>}
      {files.map(file => (
        <div className={styles.fileRow} key={file.name}>
          {file.icon}
          <div>
            <strong>{file.name}</strong>
            <div className={styles.meta}>{file.detail}</div>
          </div>
          {file.action && (
            <button type='button' className={styles.textLink} onClick={file.action}>
              {financialText('financial.view')}
            </button>
          )}
        </div>
      ))}
    </div>
  );
};
const SkillPanel: React.FC = () => {
  useFinancialLocale();
  const { data } = useReportData();
  return (
    <div className={styles.utilityPanel}>
      <div className={styles.meta}>DB-GPT Skill</div>
      <h2>financial-report-analyzer</h2>
      <p className={styles.sectionDescription}>
        {financialText('financial.extract_financial_metrics_calculate_ratios_create_charts_and_assembl')}
      </p>
      <dl className={styles.driverTable}>
        <div>
          <dt>{financialText('financial.extract_metrics')}</dt>
          <dd>extract_financials.py</dd>
        </div>
        <div>
          <dt>{financialText('financial.calculate_ratios')}</dt>
          <dd>calculate_ratios.py</dd>
        </div>
        <div>
          <dt>{financialText('financial.create_charts')}</dt>
          <dd>generate_charts.py</dd>
        </div>
      </dl>
      <details className={styles.developerNote}>
        <summary>{financialText('financial.about_this_workspace')}</summary>
        <p>{capabilityNote()}</p>
        <p>Run #{data.report.run.id}</p>
      </details>
    </div>
  );
};

const FinancialAnalysisWorkspace: React.FC<{
  comparisonAccess?: ComparisonAccess;
  revisionAccess?: ReportRevisionAccess;
  citationTarget?: FinancialCitationTarget | null;
  onTopicRetry?: (topicId: string) => void;
  busy?: boolean;
  embedded?: boolean;
  onNewReport?: () => void;
  sourceAccess?: SourcePreviewAccess;
  analysisActions?: AnalysisActions;
  questionAccess?: ReportQuestionAccess;
  exportAccess?: ReportExportAccess;
}> = ({
  comparisonAccess,
  revisionAccess,
  citationTarget,
  embedded = false,
  onNewReport,
  sourceAccess,
  analysisActions,
  questionAccess,
  exportAccess,
  onTopicRetry,
  busy,
}) => {
  useFinancialLocale();
  const { data, sourceDocumentMap } = useReportData();
  const runState = reportRunState(data);
  const router = useRouter();
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>('report');
  const [financialTab, setFinancialTab] = useState('overview');
  const [activeStepId, setActiveStepId] = useState<string | undefined>(data.steps[0]?.id);
  const [selection, setSelection] = useState<EvidenceSelection>({ findingId: data.sections.overview.findingIds[0] });
  const [previewEvidence, setPreviewEvidence] = useState<EvidenceExcerpt | null>(null);
  const [agentCollapsed, setAgentCollapsed] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const reportScroll = useRef(0);
  const appliedCitation = useRef<number | null>(null);

  useEffect(() => {
    if (!citationTarget || appliedCitation.current === citationTarget.requestId) return;
    const next = resolveFinancialCitation(data, citationTarget);
    if (!next) return;
    appliedCitation.current = citationTarget.requestId;
    setSelection(next);
    setPreviewEvidence(null);
    setWorkspaceTab('evidence');
  }, [citationTarget, data]);

  const switchWorkspace = (next: WorkspaceTab) => {
    if (workspaceTab === 'report') reportScroll.current = scrollRef.current?.scrollTop || 0;
    setWorkspaceTab(next);
    setPreviewEvidence(null);
    requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: next === 'report' ? reportScroll.current : 0 }));
  };
  const openEvidence = (next: EvidenceSelection) => {
    setSelection(next);
    switchWorkspace('evidence');
  };
  const openSource = (evidence: EvidenceExcerpt) => {
    setSelection({ evidenceId: evidence.id });
    if (workspaceTab === 'report') reportScroll.current = scrollRef.current?.scrollTop || 0;
    setWorkspaceTab('evidence');
    setPreviewEvidence(evidence);
    requestAnimationFrame(() => scrollRef.current?.scrollTo({ top: 0 }));
  };
  const financialTabs =
    data.mode === 'comparison'
      ? [
          {
            key: 'overview',
            label: financialText('financial.overview'),
            content: <ComparisonSections data={data} section='overview' onOpenEvidence={openEvidence} />,
          },
          {
            key: 'profitability',
            label: financialText('financial.earnings_quality'),
            content: <ComparisonSections data={data} section='profitability' onOpenEvidence={openEvidence} />,
          },
          {
            key: 'cashflow',
            label: financialText('financial.cash_flow'),
            content: <ComparisonSections data={data} section='cashflow' onOpenEvidence={openEvidence} />,
          },
          {
            key: 'balance',
            label: financialText('financial.assets_and_liabilities'),
            content: <ComparisonSections data={data} section='balance' onOpenEvidence={openEvidence} />,
          },
        ]
      : [
          {
            key: 'overview',
            label: financialText('financial.overview'),
            content: <OverviewTab onOpenEvidence={openEvidence} />,
          },
          {
            key: 'profitability',
            label: financialText('financial.earnings_quality'),
            content: <ProfitabilityTab onOpenEvidence={openEvidence} />,
          },
          {
            key: 'cashflow',
            label: financialText('financial.cash_flow'),
            content: <CashFlowTab onOpenEvidence={openEvidence} />,
          },
          {
            key: 'balance',
            label: financialText('financial.assets_and_liabilities'),
            content: <BalanceTab onOpenEvidence={openEvidence} />,
          },
          {
            key: 'statements',
            label: financialText('financial.key_statements'),
            content: <StatementsTab onOpenEvidence={openEvidence} />,
          },
        ];
  const previewDocument = previewEvidence ? sourceDocumentMap[previewEvidence.sourceDocumentId] : null;

  return (
    <main className={styles.workspace} data-embedded={embedded || undefined}>
      {!embedded && (
        <header className={styles.header}>
          <button type='button' onClick={() => router.push('/')} className={styles.breadcrumb}>
            <RobotOutlined />
            <strong>DB-GPT</strong>
            <span>/</span>
            <span>Agent Workspace</span>
          </button>
          {onNewReport && (
            <button type='button' className={styles.textLink} onClick={onNewReport}>
              {financialText('financial.analyze_another_report')}
            </button>
          )}
          <span className={styles.completed} aria-label={financialText('financial.report_status')}>
            {runState.complete && <CheckCircleFilled />} {runState.label}
          </span>
        </header>
      )}
      <div className={styles.columns} data-agent-collapsed={embedded || agentCollapsed}>
        {!embedded && (
          <section
            className={styles.agentRail}
            aria-label={financialText('financial.db_gpt_agent_task')}
            hidden={agentCollapsed}
          >
            <div className={styles.agentScroll}>
              <AgentRunPanel
                onFinancialCitationClick={citation => {
                  const next = resolveFinancialCitation(data, citation);
                  if (next) openEvidence(next);
                }}
                activeStepId={activeStepId}
                onStepSelect={id => {
                  setActiveStepId(id);
                  switchWorkspace('execution');
                }}
                onOpenArtifact={() => switchWorkspace('report')}
                onOpenFiles={() => switchWorkspace('files')}
              />
            </div>
            <AskDbGPTDock onOpenEvidence={openEvidence} questionAccess={questionAccess} />
          </section>
        )}
        <section className={styles.computer} aria-label='DB-GPT Computer'>
          {!embedded && (
            <div className={styles.computerHeader}>
              <div>
                <button
                  type='button'
                  onClick={() => setAgentCollapsed(value => !value)}
                  aria-label={
                    agentCollapsed
                      ? financialText('financial.expand_agent_panel')
                      : financialText('financial.collapse_agent_panel')
                  }
                  aria-expanded={!agentCollapsed}
                >
                  {agentCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                </button>
                <DesktopOutlined />
                <span>DB-GPT Computer</span>
              </div>
              <Tooltip title={capabilityNote}>
                <button type='button' aria-label={financialText('financial.about_this_workspace')}>
                  <InfoCircleOutlined />
                </button>
              </Tooltip>
            </div>
          )}
          <nav className={styles.workspaceNav} aria-label={financialText('financial.computer_workspace')}>
            {embedded && (
              <span className={styles.completed} aria-label={financialText('financial.report_status')}>
                {runState.label}
              </span>
            )}
            {workspaceTabs
              .filter(tab => !embedded || tab.key !== 'skill')
              .map(tab => (
                <button
                  type='button'
                  key={tab.key}
                  aria-current={workspaceTab === tab.key ? 'page' : undefined}
                  onClick={() => switchWorkspace(tab.key)}
                >
                  {tab.icon}
                  <span>{tab.label}</span>
                </button>
              ))}
          </nav>
          <div ref={scrollRef} className={styles.artifactScroll}>
            {workspaceTab === 'report' && (
              <>
                <ArtifactContext comparisonAccess={comparisonAccess} revisionAccess={revisionAccess} />
                <nav className={styles.reportNav} aria-label={financialText('financial.financial_report_sections')}>
                  {financialTabs.map(tab => (
                    <button
                      type='button'
                      key={tab.key}
                      aria-current={financialTab === tab.key ? 'page' : undefined}
                      onClick={() => {
                        setFinancialTab(tab.key);
                        reportScroll.current = 0;
                        scrollRef.current?.scrollTo({ top: 0 });
                      }}
                    >
                      {tab.label}
                    </button>
                  ))}
                </nav>
                <div className={styles.reportBody}>{financialTabs.find(tab => tab.key === financialTab)?.content}</div>
              </>
            )}
            {workspaceTab === 'execution' && (
              <ExecutionProcessPanel
                activeStepId={activeStepId}
                onStepSelect={setActiveStepId}
                analysisActions={analysisActions}
                onTopicRetry={onTopicRetry}
                busy={busy}
              />
            )}
            {workspaceTab === 'files' && (
              <FilesPanel
                onOpenSource={openSource}
                onOpenArtifact={() => switchWorkspace('report')}
                exportAccess={exportAccess}
              />
            )}
            {workspaceTab === 'skill' && <SkillPanel />}
            {workspaceTab === 'evidence' && (
              <>
                <div className={styles.evidenceToolbar}>
                  <button type='button' className={styles.textLink} onClick={() => switchWorkspace('report')}>
                    <ArrowLeftOutlined /> {financialText('financial.back_to_report')}
                  </button>
                  <span className={styles.meta}>{financialText('financial.evidence_trail')}</span>
                </div>
                {previewEvidence && previewDocument ? (
                  <SourcePreviewPanel
                    sourceAccess={sourceAccess}
                    evidence={previewEvidence}
                    document={previewDocument}
                    onBack={() => {
                      setPreviewEvidence(null);
                      setSelection({ evidenceId: previewEvidence.id });
                    }}
                  />
                ) : (
                  <EvidencePanel
                    selection={selection}
                    onFindingChange={id => {
                      setSelection({ findingId: id });
                      scrollRef.current?.scrollTo({ top: 0 });
                    }}
                    onOpenSource={openSource}
                  />
                )}
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  );
};
const FinancialAnalysisPage: React.FC<{
  comparisonAccess?: ComparisonAccess;
  revisionAccess?: ReportRevisionAccess;
  citationTarget?: FinancialCitationTarget | null;
  onTopicRetry?: (topicId: string) => void;
  busy?: boolean;
  embedded?: boolean;
  data: FinancialReportData;
  onNewReport?: () => void;
  sourceAccess?: SourcePreviewAccess;
  analysisActions?: AnalysisActions;
  questionAccess?: ReportQuestionAccess;
  exportAccess?: ReportExportAccess;
}> = ({
  comparisonAccess,
  revisionAccess,
  citationTarget,
  data,
  embedded,
  onNewReport,
  sourceAccess,
  analysisActions,
  questionAccess,
  exportAccess,
  onTopicRetry,
  busy,
}) => (
  <ReportDataProvider key={`${data.report.id}:${data.report.run.id}:${data.revision}`} data={data}>
    <FinancialAnalysisWorkspace
      comparisonAccess={comparisonAccess}
      revisionAccess={revisionAccess}
      citationTarget={citationTarget}
      onTopicRetry={onTopicRetry}
      busy={busy}
      embedded={embedded}
      onNewReport={onNewReport}
      sourceAccess={sourceAccess}
      analysisActions={analysisActions}
      questionAccess={questionAccess}
      exportAccess={exportAccess}
    />
  </ReportDataProvider>
);
export default FinancialAnalysisPage;
