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
import React, { useRef, useState } from 'react';
import AgentRunPanel from './AgentRunPanel';
import AskDbGPTDock from './AskDbGPTDock';
import EvidencePanel from './EvidencePanel';
import ExecutionProcessPanel, { AnalysisActions } from './ExecutionProcessPanel';
import { ReportDataProvider, useReportData } from './ReportDataContext';
import ReportExports from './ReportExports';
import { BalanceTab, CashFlowTab, OverviewTab, ProfitabilityTab, StatementsTab } from './ReportSections';
import SourcePreviewPanel from './SourcePreviewPanel';
import styles from './financial-analysis.module.css';
import { reportRunState } from './report-data';
import {
  EvidenceExcerpt,
  EvidenceSelection,
  ReportData,
  ReportExportAccess,
  ReportQuestionAccess,
  SourcePreviewAccess,
} from './types';

type WorkspaceTab = 'report' | 'execution' | 'files' | 'skill' | 'evidence';
const workspaceTabs: Array<{ key: WorkspaceTab; label: string; icon: React.ReactNode }> = [
  { key: 'report', label: '分析报告', icon: <FileTextOutlined /> },
  { key: 'execution', label: '执行过程', icon: <DesktopOutlined /> },
  { key: 'files', label: '文件', icon: <FolderOpenOutlined /> },
  { key: 'skill', label: 'financial-report-analyzer', icon: <AppstoreOutlined /> },
  { key: 'evidence', label: '证据', icon: <FileSearchOutlined /> },
];
const capabilityNote = '当前页面展示所选报告数据。追问仅依据当前报告，缺少的指标与来源会明确标记。';

const ArtifactContext: React.FC = () => {
  const {
    data: { report, documents },
  } = useReportData();
  return (
    <section className={styles.reportContext}>
      <div className={styles.contextByline}>
        Financial Analysis <span>／ {report.run.skillName}</span>
      </div>
      <h1>{report.companyName}</h1>
      <div className={styles.meta}>
        {report.title} · {report.statementScope} · {report.currency} ·{' '}
        {documents.map(item => item.fileName).join(' / ') || '来源文件未提供'}
      </div>
    </section>
  );
};

const FilesPanel: React.FC<{
  onOpenSource: (evidence: EvidenceExcerpt) => void;
  onOpenArtifact: () => void;
  exportAccess?: ReportExportAccess;
}> = ({ onOpenSource, onOpenArtifact, exportAccess }) => {
  const { data } = useReportData();
  const files = [
    ...data.documents.map(document => {
      const evidence = data.evidence.find(item => item.sourceDocumentId === document.id);
      return {
        name: document.fileName,
        detail: `上传资料 · PDF${document.sizeBytes === undefined ? '' : ` · ${(document.sizeBytes / 1024 / 1024).toFixed(1)} MB`}`,
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
      <h2>任务文件</h2>
      <p className={styles.sectionDescription}>本轮输入资料与分析交付物</p>
      {exportAccess && <ReportExports access={exportAccess} />}
      {!files.length && <p className={styles.meta}>暂无文件</p>}
      {files.map(file => (
        <div className={styles.fileRow} key={file.name}>
          {file.icon}
          <div>
            <strong>{file.name}</strong>
            <div className={styles.meta}>{file.detail}</div>
          </div>
          {file.action && (
            <button type='button' className={styles.textLink} onClick={file.action}>
              查看 →
            </button>
          )}
        </div>
      ))}
    </div>
  );
};
const SkillPanel: React.FC = () => {
  const { data } = useReportData();
  return (
    <div className={styles.utilityPanel}>
      <div className={styles.meta}>DB-GPT Skill</div>
      <h2>financial-report-analyzer</h2>
      <p className={styles.sectionDescription}>提取财务指标、执行比率计算、生成图表并形成财务分析报告。</p>
      <dl className={styles.driverTable}>
        <div>
          <dt>提取指标</dt>
          <dd>extract_financials.py</dd>
        </div>
        <div>
          <dt>比率计算</dt>
          <dd>calculate_ratios.py</dd>
        </div>
        <div>
          <dt>生成图表</dt>
          <dd>generate_charts.py</dd>
        </div>
      </dl>
      <details className={styles.developerNote}>
        <summary>关于此工作区</summary>
        <p>{capabilityNote}</p>
        <p>Run #{data.report.run.id}</p>
      </details>
    </div>
  );
};

const FinancialAnalysisWorkspace: React.FC<{
  onTopicRetry?: (topicId: string) => void;
  busy?: boolean;
  embedded?: boolean;
  onNewReport?: () => void;
  sourceAccess?: SourcePreviewAccess;
  analysisActions?: AnalysisActions;
  questionAccess?: ReportQuestionAccess;
  exportAccess?: ReportExportAccess;
}> = ({
  embedded = false,
  onNewReport,
  sourceAccess,
  analysisActions,
  questionAccess,
  exportAccess,
  onTopicRetry,
  busy,
}) => {
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
  const financialTabs = [
    { key: 'overview', label: 'Overview', content: <OverviewTab onOpenEvidence={openEvidence} /> },
    { key: 'profitability', label: '盈利质量', content: <ProfitabilityTab onOpenEvidence={openEvidence} /> },
    { key: 'cashflow', label: '现金流', content: <CashFlowTab onOpenEvidence={openEvidence} /> },
    { key: 'balance', label: '资产负债', content: <BalanceTab onOpenEvidence={openEvidence} /> },
    { key: 'statements', label: '关键报表', content: <StatementsTab onOpenEvidence={openEvidence} /> },
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
              分析另一份报告
            </button>
          )}
          <span className={styles.completed} aria-label='报告状态'>
            {runState.complete && <CheckCircleFilled />} {runState.label}
          </span>
        </header>
      )}
      <div className={styles.columns} data-agent-collapsed={embedded || agentCollapsed}>
        {!embedded && (
          <section className={styles.agentRail} aria-label='DB-GPT Agent 任务' hidden={agentCollapsed}>
            <div className={styles.agentScroll}>
              <AgentRunPanel
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
                  aria-label={agentCollapsed ? '展开 Agent 面板' : '折叠 Agent 面板'}
                  aria-expanded={!agentCollapsed}
                >
                  {agentCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
                </button>
                <DesktopOutlined />
                <span>DB-GPT Computer</span>
              </div>
              <Tooltip title={capabilityNote}>
                <button type='button' aria-label='关于此工作区'>
                  <InfoCircleOutlined />
                </button>
              </Tooltip>
            </div>
          )}
          <nav className={styles.workspaceNav} aria-label='Computer 工作区'>
            {embedded && (
              <span className={styles.completed} aria-label='报告状态'>
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
                <ArtifactContext />
                <nav className={styles.reportNav} aria-label='财务分析章节'>
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
                    <ArrowLeftOutlined /> 返回分析报告
                  </button>
                  <span className={styles.meta}>证据链</span>
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
  onTopicRetry?: (topicId: string) => void;
  busy?: boolean;
  embedded?: boolean;
  data: ReportData;
  onNewReport?: () => void;
  sourceAccess?: SourcePreviewAccess;
  analysisActions?: AnalysisActions;
  questionAccess?: ReportQuestionAccess;
  exportAccess?: ReportExportAccess;
}> = ({
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
