import type { ArtifactItem, ExecutionStep, ThinkingSection } from '@/new-components/chat/content/ManusLeftPanel';
import dynamic from 'next/dynamic';
import React, { useMemo } from 'react';
import { useReportData } from './ReportDataContext';
import type { FinancialCitation } from './report-citations';
import { isDefined, reportRunState } from './report-data';
import { AgentExecutionStep } from './types';

const ManusLeftPanel = dynamic(() => import('@/new-components/chat/content/ManusLeftPanel'), {
  ssr: false,
  loading: () => (
    <div className='space-y-4 p-5'>
      <div className='ml-auto h-20 w-4/5 animate-pulse rounded-2xl bg-gray-100 dark:bg-white/[0.05]' />
      <div className='h-44 animate-pulse rounded-xl bg-gray-50 dark:bg-white/[0.03]' />
      <div className='h-28 animate-pulse rounded-xl bg-gray-50 dark:bg-white/[0.03]' />
    </div>
  ),
});

interface AgentRunPanelProps {
  onFinancialCitationClick?: (citation: FinancialCitation) => void;
  activeStepId?: string;
  onStepSelect: (stepId: string) => void;
  onOpenArtifact: () => void;
  onOpenFiles: () => void;
}

const toExecutionStep = (step: AgentExecutionStep): ExecutionStep => ({
  id: step.id,
  type: step.type === 'analysis' ? 'task' : step.type,
  title: step.title,
  subtitle: step.script || step.tool,
  description: step.detail,
  status: step.status === 'failed' ? 'error' : step.status,
  action: step.tool,
  actionInput: step.script ? { script: step.script } : undefined,
});

const AgentRunPanel: React.FC<AgentRunPanelProps> = ({
  activeStepId,
  onStepSelect,
  onOpenArtifact,
  onOpenFiles,
  onFinancialCitationClick,
}) => {
  const { data } = useReportData();
  const sections = useMemo<ThinkingSection[]>(
    () =>
      data.agent.groups.map(group => {
        const steps = group.stepIds
          .map(id => data.steps.find(step => step.id === id))
          .filter(isDefined)
          .map(toExecutionStep);
        return { ...group, steps, isCompleted: steps.length > 0 && steps.every(step => step.status === 'completed') };
      }),
    [data],
  );
  const inputFiles = data.documents.map((document, ordinal) => ({
    file_id: document.fileId || document.id,
    name: document.fileName,
    size: document.sizeBytes ?? 0,
    media_type: 'application/pdf',
    kind: 'document',
    status: 'ready' as const,
    ordinal,
  }));
  const artifacts: ArtifactItem[] = data.artifacts
    .filter(item => item.kind === 'html')
    .map(item => ({
      id: item.id,
      name: item.name,
      type: 'html',
      content: { reportId: data.report.id },
      createdAt: data.report.run.completedAt ? new Date(data.report.run.completedAt).getTime() : 0,
      downloadable: false,
      mimeType: 'text/html',
      size: item.sizeBytes,
    }));
  return (
    <ManusLeftPanel
      onFinancialCitationClick={onFinancialCitationClick}
      sections={sections}
      activeStepId={activeStepId}
      onStepClick={stepId => onStepSelect(stepId)}
      isWorking={reportRunState(data).working}
      userQuery={data.agent.userQuery}
      attachedFiles={inputFiles}
      attachedSkill={{ name: data.report.run.skillName, id: data.report.run.skillName }}
      assistantText={data.agent.summary}
      modelName={data.report.run.modelName}
      artifacts={artifacts}
      onArtifactClick={onOpenArtifact}
      onViewAllFiles={onOpenFiles}
    />
  );
};

export default AgentRunPanel;
