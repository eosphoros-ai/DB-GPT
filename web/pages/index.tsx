import { ChatContext } from '@/app/chat-context';
import ModelIcon from '@/new-components/chat/content/ModelIcon';
import { copyText } from '@/utils/clipboard';
import axios from '@/utils/ctx-axios';
import {
  ArrowUpOutlined,
  CloseOutlined,
  DeleteOutlined,
  LeftOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MessageOutlined,
  PlusOutlined,
  RightOutlined,
  RobotOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { Button, ConfigProvider, Input, Select, Skeleton, Tooltip, message } from 'antd';
import { NextPage } from 'next';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import ManusLeftPanel, { ArtifactItem, StepType, ThinkingSection } from '@/new-components/chat/content/ManusLeftPanel';
import ManusRightPanel, {
  ActiveStepInfo,
  ExecutionOutput as ManusExecutionOutput,
  PanelView,
} from '@/new-components/chat/content/ManusRightPanel';

const ASSISTANT_TITLE = '中涣问数';
const BRAND_LOGO = '/zhongke-zhonghuan-logo.png';
const CHAT_MODE = 'chat_react_agent';

/* ───────── helpers ───────── */

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return '刚刚';
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour}小时前`;
  const diffDay = Math.floor(diffHour / 24);
  if (diffDay < 7) return `${diffDay}天前`;
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

const generateUUID = () =>
  'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });

const sanitizeBrandText = (text: string): string => text.replace(/\b(?:DB-GPT|DBGPT|dbgpt)\b/g, '中涣信息');

const cleanFinalContent = (text: string): string => {
  let cleaned = text.replace(/\\n/g, '\n').trim();
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
  cleaned = cleaned.replace(/"\s*\}\s*$/, '').trim();
  // Strip ReAct reasoning prefixes
  cleaned = cleaned
    .replace(/^(Thought|Action|Action Input|Observation|Phase|Action Intention|Action Reason):\s*/gm, '')
    .trim();
  // Strip bracket annotations like [Pasted ~ N lines]
  cleaned = cleaned.replace(/\[Pasted\s*~?\s*\d*\s*lines?\]/gi, '').trim();
  // Strip trailing reasoning blocks before terminate
  const terminateIdx = cleaned.toLowerCase().indexOf('terminate');
  if (terminateIdx > 0) {
    const afterTerminate = cleaned.slice(terminateIdx + 9).trim();
    const resultMatch = afterTerminate.match(/"result"\s*:\s*"((?:[^"\\]|\\.)*)"/s);
    if (resultMatch) {
      cleaned = resultMatch[1].replace(/\\"/g, '"').replace(/\\n/g, '\n');
    }
  }
  return sanitizeBrandText(cleaned);
};

/* ───────── types ───────── */

interface ChatMessage {
  id: string;
  role: 'human' | 'view';
  context: string;
  thinking?: boolean;
  order?: number;
  model_name?: string;
  attachedFile?: { name: string; size: number; type: string };
  taskPlan?: TaskItem[];
}

interface ConversationItem {
  conv_uid: string;
  user_input?: string;
  chat_mode?: string;
  select_param?: string;
  gmt_created?: string;
}

interface Round {
  humanMsg: ChatMessage | null;
  viewMsg: ChatMessage | null;
}

interface ExecutionStep {
  id: string;
  step?: number;
  title: string;
  detail: string;
  status: 'running' | 'done' | 'failed';
  action?: string;
  actionInput?: string;
  phase?: string;
  todoMeta?: any;
  elapsedMs?: number;
}

interface ExecutionOutput {
  output_type: string;
  content: any;
}

interface ExecutionState {
  steps: ExecutionStep[];
  outputs: Record<string, ExecutionOutput[]>;
  activeStepId: string | null;
  collapsed: boolean;
  stepThoughts: Record<string, string>;
}

interface TaskItem {
  id: string;
  content: string;
  status: 'pending' | 'in_progress' | 'completed';
}

/* ───────── convertToManusFormat ───────── */

const getStepType = (title?: string, action?: string): StepType => {
  const actionLower = (action || '').toLowerCase();
  if (
    actionLower.includes('skill') ||
    actionLower === 'execute_skill_script_file' ||
    actionLower === 'get_skill_resource' ||
    actionLower === 'select_skill' ||
    actionLower === 'load_skill'
  )
    return 'skill';
  if (actionLower === 'shell_interpreter') return 'bash';
  if (actionLower === 'sql_query') return 'sql';
  const lower = (title || '').toLowerCase();
  if (lower.includes('sql_query') || lower.includes('sql query') || lower.includes('sql查询')) return 'sql';
  if (lower.includes('read') || lower.includes('load')) return 'read';
  if (lower.includes('edit')) return 'edit';
  if (lower.includes('write') || lower.includes('save')) return 'write';
  if (lower.includes('bash') || lower.includes('execute') || lower.includes('command') || lower.includes('shell'))
    return 'bash';
  if (lower.includes('grep') || lower.includes('search')) return 'grep';
  if (lower.includes('glob') || lower.includes('find')) return 'glob';
  if (lower.includes('html')) return 'html';
  if (lower.includes('python') || lower.includes('code')) return 'python';
  if (lower.includes('skill')) return 'skill';
  if (lower.includes('task')) return 'task';
  return 'other';
};

const getStepStatus = (status: string): 'pending' | 'running' | 'completed' | 'error' => {
  if (status === 'running') return 'running';
  if (status === 'done') return 'completed';
  if (status === 'failed') return 'error';
  return 'pending';
};

const convertToManusFormat = (
  execution: ExecutionState | undefined,
  t?: (key: string) => string,
): {
  sections: ThinkingSection[];
  activeStep: ActiveStepInfo | null;
  outputs: ManusExecutionOutput[];
  stepThoughts: Record<string, string>;
} => {
  if (!execution || !execution.steps.length) {
    return { sections: [], activeStep: null, outputs: [], stepThoughts: execution?.stepThoughts || {} };
  }
  const steps = execution.steps
    .filter(step => !(step.detail || '').toLowerCase().includes('action: terminate'))
    .map(step => {
      const cleanDetail = step.detail?.replace(/^Thought:.*\n?/gm, '').trim();
      return {
        id: step.id,
        type: getStepType(step.title, step.action),
        title: step.title || `Step ${step.step}`,
        subtitle: cleanDetail?.split('\n')[0]?.slice(0, 80),
        description: cleanDetail || undefined,
        phase: (step as any).phase,
        status: getStepStatus(step.status),
        elapsedMs: step.elapsedMs,
      };
    });
  const sections: ThinkingSection[] = [
    {
      id: 'section-execution',
      title: t ? t('execution_steps') : '执行步骤',
      isCompleted: steps.every(s => s.status === 'completed'),
      steps,
    },
  ];
  let activeStep: ActiveStepInfo | null = null;
  if (execution.activeStepId) {
    const step = execution.steps.find(s => s.id === execution.activeStepId);
    if (step) {
      const cleanDetail = step.detail?.replace(/^Thought:.*\n?/gm, '').trim();
      activeStep = {
        id: step.id,
        type: getStepType(step.title, step.action),
        title: step.title || `Step ${step.step}`,
        subtitle: cleanDetail?.split('\n')[0]?.slice(0, 80),
        status: getStepStatus(step.status),
        detail: cleanDetail,
        action: step.action,
        actionInput: step.actionInput,
        elapsedMs: step.elapsedMs,
      };
    }
  }
  const outputs: ManusExecutionOutput[] = execution.activeStepId
    ? (execution.outputs[execution.activeStepId] || []).map(o => ({
        output_type: o.output_type as any,
        content: o.content,
        timestamp: Date.now(),
      }))
    : [];
  return { sections, activeStep, outputs, stepThoughts: execution?.stepThoughts || {} };
};

/* ───────── Artifacts ───────── */

const buildArtifactsFromExecution = (messageId: string, execution: ExecutionState): ArtifactItem[] => {
  const artifacts: ArtifactItem[] = [];
  const now = Date.now();
  execution.steps.forEach(step => {
    const stepOutputs = execution.outputs[step.id] || [];
    stepOutputs.forEach((output, oIdx) => {
      if (output.output_type === 'html') {
        const htmlContent =
          typeof output.content === 'string'
            ? output.content
            : output.content?.content || output.content?.html || String(output.content);
        const title = output.content?.title || 'Report';
        artifacts.push({
          id: `${messageId}-html-${step.id}-${oIdx}`,
          type: 'html',
          name: `${title}.html`,
          content: htmlContent,
          createdAt: now,
          downloadable: true,
        });
      } else if (output.output_type === 'image') {
        const imgUrl =
          typeof output.content === 'string'
            ? output.content
            : output.content?.url || output.content?.src || String(output.content);
        const imgName = imgUrl.split('/').pop() || `image_${oIdx}.png`;
        artifacts.push({
          id: `${messageId}-img-${step.id}-${oIdx}`,
          type: 'image',
          name: imgName.replace(/^[a-f0-9]{8}_/, ''),
          content: imgUrl,
          createdAt: now,
          downloadable: true,
        });
      } else if (output.output_type === 'code') {
        const codeStr = String(output.content || '').trim();
        if (codeStr) {
          artifacts.push({
            id: `${messageId}-code-${step.id}-${oIdx}`,
            type: 'code',
            name: `code_${step.id}.py`,
            content: codeStr,
            createdAt: now,
            downloadable: true,
          });
        }
      }
    });
  });
  return artifacts;
};

const downloadArtifact = async (artifact: ArtifactItem) => {
  const triggerBlobDownload = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  switch (artifact.type) {
    case 'image': {
      const imgUrl =
        typeof artifact.content === 'string'
          ? artifact.content
          : artifact.content?.url || artifact.content?.src || String(artifact.content);
      const resolvedUrl = imgUrl.startsWith('/images/') ? `${process.env.API_BASE_URL || ''}${imgUrl}` : imgUrl;
      try {
        const resp = await fetch(resolvedUrl);
        const blob = await resp.blob();
        triggerBlobDownload(blob, artifact.name || 'image.png');
      } catch {
        const a = document.createElement('a');
        a.href = resolvedUrl;
        a.download = artifact.name || 'image.png';
        a.target = '_blank';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
      break;
    }
    case 'html': {
      const htmlContent =
        typeof artifact.content === 'string'
          ? artifact.content
          : artifact.content?.content || artifact.content?.html || String(artifact.content);
      triggerBlobDownload(new Blob([htmlContent], { type: 'text/html' }), artifact.name || 'report.html');
      break;
    }
    case 'code': {
      triggerBlobDownload(new Blob([String(artifact.content)], { type: 'text/plain' }), artifact.name || 'code.py');
      break;
    }
    default: {
      triggerBlobDownload(new Blob([String(artifact.content)]), artifact.name || 'file');
    }
  }
};

/* ───────── ChatInputBox ───────── */

interface ChatInputBoxProps {
  query: string;
  onQueryChange: (value: string) => void;
  onSend: () => void;
  loading: boolean;
  canSend: boolean;
  isZhInput: boolean;
  setIsZhInput: (v: boolean) => void;
  model: string;
  modelList: string[];
  onModelChange: (v: string) => void;
  renderModelOption: (modelName: string, showIcon?: boolean) => React.ReactNode;
  showBrand?: boolean;
}

const ChatInputBox: React.FC<ChatInputBoxProps> = ({
  query,
  onQueryChange,
  onSend,
  loading,
  canSend,
  isZhInput,
  setIsZhInput,
  model,
  modelList,
  onModelChange,
  renderModelOption,
  showBrand = false,
}) => (
  <>
    <div className='rounded-[28px] border border-gray-200 bg-white px-4 py-3 shadow-[0_2px_18px_rgba(0,0,0,0.08)] dark:border-[#3a3a3a] dark:bg-[#212121]'>
      <Input.TextArea
        value={query}
        onChange={e => onQueryChange(e.target.value)}
        onPressEnter={e => {
          if (!e.shiftKey && !isZhInput) {
            e.preventDefault();
            onSend();
          }
        }}
        onCompositionStart={() => setIsZhInput(true)}
        onCompositionEnd={() => setIsZhInput(false)}
        placeholder='给中涣问数发送消息'
        autoSize={{ minRows: 1, maxRows: 5 }}
        disabled={loading}
        className='resize-none !border-none !bg-transparent !px-0 !py-0 !text-base !leading-7 !shadow-none'
      />
      <div className='mt-2 flex items-center justify-between gap-3'>
        <div className='flex min-w-0 items-center gap-2'>
          {showBrand && <span className='hidden text-xs text-gray-400 sm:inline'>中科中涣 · 数据助理</span>}
          <Select
            aria-label='选择模型'
            value={modelList.length > 0 ? model || undefined : '未检测到可用模型'}
            placeholder='选择模型'
            disabled={modelList.length === 0}
            optionLabelProp='label'
            popupMatchSelectWidth={false}
            onChange={onModelChange}
            className='min-w-[150px]'
          >
            {modelList.length > 0 ? (
              modelList.map(item => (
                <Select.Option key={item} value={item} label={renderModelOption(item)}>
                  {renderModelOption(item)}
                </Select.Option>
              ))
            ) : (
              <Select.Option value='未检测到可用模型' label={renderModelOption('未检测到可用模型', false)}>
                {renderModelOption('未检测到可用模型', false)}
              </Select.Option>
            )}
          </Select>
        </div>
        <Button
          type='primary'
          shape='circle'
          size='large'
          icon={<ArrowUpOutlined />}
          loading={loading}
          disabled={!canSend}
          onClick={onSend}
          className='!h-8 !w-8 !min-w-8 !bg-[#111827] !text-white disabled:!bg-gray-200 disabled:!text-gray-400 dark:!bg-white dark:!text-[#111111] dark:disabled:!bg-[#3a3a3a] dark:disabled:!text-gray-500'
        />
      </div>
    </div>
    <div className='mt-2 text-center text-xs text-gray-400'>内容由 AI 生成，请结合业务数据核验。</div>
  </>
);

/* ───────── Component ───────── */

const ZhonghuanAssistant: NextPage = () => {
  const { t } = useTranslation();
  const router = useRouter();
  const { model, modelList, setModel } = useContext(ChatContext);
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [isZhInput, setIsZhInput] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [conversationList, setConversationList] = useState<ConversationItem[]>([]);
  const [listLoading, setListLoading] = useState(false);
  const [historySearch, setHistorySearch] = useState('');

  // Agent execution state
  const [executionMap, setExecutionMap] = useState<Record<string, ExecutionState>>({});
  const [, setActiveMessageId] = useState<string | null>(null);
  const [activeViewMsgId, setActiveViewMsgId] = useState<string | null>(null);
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [rightPanelView, setRightPanelView] = useState<PanelView>('execution');
  const [, setTaskPlan] = useState<TaskItem[]>([]);
  const [streamingSummary, setStreamingSummary] = useState('');
  const [summaryComplete, setSummaryComplete] = useState(false);
  const terminatedStepIdsRef = useRef(new Set<string>());

  // Load conversation from URL
  useEffect(() => {
    const convId = router.query.id as string | undefined;
    if (convId && convId !== conversationId) loadConversation(convId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.query.id]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const canSend = useMemo(() => !!query.trim() && !loading, [loading, query]);

  const updateAssistantMessage = (messageId: string, updater: (msg: ChatMessage) => ChatMessage) => {
    setMessages(prev => prev.map(item => (item.id === messageId && item.role === 'view' ? updater(item) : item)));
  };

  /* ── conversation list ── */

  const fetchConversationList = useCallback(async () => {
    setListLoading(true);
    try {
      const response: any = await axios.get('/api/v1/chat/dialogue/list');
      const result = response?.success !== undefined ? response : response?.data;
      setConversationList(result?.data || result || []);
    } catch (_e) {
      setConversationList([]);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConversationList();
  }, [fetchConversationList]);

  /* ── load conversation (with execution restore) ── */

  const restoreFromHistory = (
    historyMessages: { role: string; context: string; order?: number; model_name?: string }[],
  ) => {
    const newMessages: ChatMessage[] = [];
    const newExecMap: Record<string, ExecutionState> = {};

    historyMessages.forEach(msg => {
      if (msg.role === 'human') {
        newMessages.push({ id: generateUUID(), role: 'human', context: msg.context, order: msg.order });
      } else if (msg.role === 'view') {
        const viewId = generateUUID();
        let payload: any = null;
        try {
          payload = JSON.parse(msg.context);
        } catch (_e) {
          /* ignore */
        }

        if (payload && payload.version === 1 && payload.type === 'react-agent') {
          const steps: ExecutionStep[] = (payload.steps || []).map((s: any, idx: number) => ({
            id: s.id || `history-step-${idx}`,
            step: idx + 1,
            title: s.title || s.action || `Step ${idx + 1}`,
            detail: s.detail || '',
            status: (s.status === 'failed' ? 'failed' : 'done') as 'done' | 'failed',
            action: s.action,
            actionInput: s.action_input || undefined,
            todoMeta: s.todo_meta || undefined,
            elapsedMs: typeof s.elapsed_ms === 'number' ? s.elapsed_ms : undefined,
          }));
          const outputs: Record<string, ExecutionOutput[]> = {};
          const stepThoughts: Record<string, string> = {};
          (payload.steps || []).forEach((s: any, idx: number) => {
            const stepId = s.id || `history-step-${idx}`;
            if (Array.isArray(s.outputs))
              outputs[stepId] = s.outputs.map((o: any) => ({
                output_type: o.output_type || 'text',
                content: o.content,
              }));
            const thought = s.action_intention
              ? s.action_reason
                ? `${s.action_intention}\n${s.action_reason}`
                : s.action_intention
              : s.thought;
            if (thought) stepThoughts[stepId] = typeof thought === 'string' ? thought : JSON.stringify(thought);
          });
          newExecMap[viewId] = {
            steps,
            outputs,
            activeStepId: steps.length ? steps[steps.length - 1].id : null,
            collapsed: false,
            stepThoughts,
          };
          newMessages.push({
            id: viewId,
            role: 'view',
            context: cleanFinalContent(payload.final_content || ''),
            order: msg.order,
            thinking: false,
            taskPlan: Array.isArray(payload.task_plan) ? payload.task_plan : undefined,
          });
        } else {
          newMessages.push({
            id: viewId,
            role: 'view',
            context: sanitizeBrandText(msg.context || ''),
            order: msg.order,
            thinking: false,
          });
        }
      }
    });

    setMessages(newMessages);
    setExecutionMap(newExecMap);
    if (newMessages.length) {
      const lastView = [...newMessages].reverse().find(m => m.role === 'view');
      if (lastView) setActiveViewMsgId(lastView.id);
    }
  };

  const loadConversation = useCallback(
    async (convId: string) => {
      setConversationId(convId);
      setLoading(true);
      router.replace(`/?id=${convId}`, undefined, { shallow: true });
      try {
        const response: any = await axios.get(`/api/v1/chat/dialogue/messages/history?con_uid=${convId}`);
        const result = response?.success !== undefined ? response : response?.data;
        const history: any[] = result?.data || result || [];
        restoreFromHistory(
          history.map((m: any) => ({ role: m.role, context: m.context, order: m.order, model_name: m.model_name })),
        );
      } catch (_e) {
        message.error('加载对话记录失败');
      } finally {
        setLoading(false);
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
    [router],
  );

  /* ── delete / new ── */

  const handleDeleteConversation = useCallback(
    async (convId: string, e: React.MouseEvent) => {
      e.stopPropagation();
      try {
        await axios.post(`/api/v1/chat/dialogue/delete?con_uid=${convId}`);
        if (conversationId === convId) {
          setConversationId(null);
          setMessages([]);
          setExecutionMap({});
        }
        fetchConversationList();
      } catch (_e) {
        message.error('删除失败');
      }
    },
    [conversationId, fetchConversationList],
  );

  const handleNewChat = useCallback(() => {
    setConversationId(null);
    setMessages([]);
    setExecutionMap({});
    setQuery('');
    setTaskPlan([]);
    router.replace('/', undefined, { shallow: true });
  }, [router]);

  const handleShareConversation = useCallback(async () => {
    if (!conversationId) return;
    try {
      const response: any = await axios.post('/api/v1/chat/share', { conv_uid: conversationId });
      const result = response?.success !== undefined ? response : response?.data;
      const sharePath = result?.data?.share_url || result?.share_url;
      if (!sharePath) {
        message.error('创建分享链接失败');
        return;
      }
      const shareUrl =
        typeof window !== 'undefined' ? new URL(sharePath, window.location.origin).toString() : sharePath;
      const copied = await copyText(shareUrl);
      message[copied ? 'success' : 'error'](copied ? '分享链接已复制' : '分享链接创建成功，但复制失败');
    } catch (_e) {
      message.error('创建分享链接失败');
    }
  }, [conversationId]);

  const createConversation = useCallback(async (): Promise<string | null> => {
    try {
      const response: any = await axios.post(`/api/v1/chat/dialogue/new?chat_mode=${CHAT_MODE}`);
      const result = response?.success !== undefined ? response : response?.data;
      const newConvId = result?.data?.conv_uid || result?.conv_uid;
      if (newConvId) {
        setConversationId(newConvId);
        fetchConversationList();
      }
      return newConvId;
    } catch (_e) {
      message.error('创建对话失败');
      return null;
    }
  }, [fetchConversationList]);

  /* ── send message (react-agent SSE) ── */

  const handleStart = async (overrideInput?: string) => {
    const isResend = typeof overrideInput === 'string';
    const userInput = (isResend ? overrideInput : query).trim();
    if (!userInput || loading) return;

    let currentConvId = conversationId;
    if (!currentConvId) {
      currentConvId = await createConversation();
      if (!currentConvId) return;
    }

    const currentOrder = Math.floor(messages.length / 2) + 1;
    const humanId = generateUUID();
    const responseId = generateUUID();

    setMessages(prev => [
      ...prev,
      { id: humanId, role: 'human', context: userInput, order: currentOrder },
      { id: responseId, role: 'view', context: '', order: currentOrder, thinking: true },
    ]);
    if (!isResend) setQuery('');
    setLoading(true);
    setStreamingSummary('');
    setSummaryComplete(false);
    setActiveViewMsgId(responseId);
    terminatedStepIdsRef.current.clear();
    setExecutionMap(prev => ({
      ...prev,
      [responseId]: { steps: [], outputs: {}, activeStepId: null, collapsed: false, stepThoughts: {} },
    }));
    setActiveMessageId(responseId);
    setTaskPlan([]);

    const controller = new AbortController();

    try {
      const response = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/chat/react-agent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conv_uid: currentConvId,
          chat_mode: CHAT_MODE,
          model_name: model,
          user_input: userInput,
          temperature: 0.6,
          max_new_tokens: 8000,
          ext_info: { database_name: 'bus_info' },
        }),
        signal: controller.signal,
      });
      if (!response.body) throw new Error('No response body');

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      const processEvent = (raw: string) => {
        if (!raw.startsWith('data:')) return;
        const data = raw.slice(5).trim();
        if (!data) return;
        let payload: any;
        try {
          payload = JSON.parse(data);
        } catch (_e) {
          return;
        }

        if (payload.type === 'plan.update') {
          if (Array.isArray(payload.tasks)) {
            setTaskPlan(payload.tasks);
            setMessages(prev =>
              prev.map(msg =>
                msg.id === responseId && msg.role === 'view' ? { ...msg, taskPlan: payload.tasks } : msg,
              ),
            );
          }
          return;
        }

        if (payload.type === 'step.start') {
          const id = payload.id || `${payload.step}`;
          if (terminatedStepIdsRef.current.has(id)) return;
          setExecutionMap(prev => {
            const current = prev[responseId] || {
              steps: [],
              outputs: {},
              activeStepId: null,
              collapsed: false,
              stepThoughts: {},
            };
            const existingIdx = current.steps.findIndex(s => s.id === id);
            let nextSteps;
            if (existingIdx >= 0) {
              nextSteps = current.steps.map((step, idx) =>
                idx === existingIdx
                  ? {
                      ...step,
                      title: payload.title,
                      detail: payload.detail,
                      phase: payload.phase,
                      todoMeta: payload.todo_meta || step.todoMeta,
                      status: 'running' as const,
                    }
                  : step.status === 'running'
                    ? { ...step, status: 'done' as const }
                    : step,
              );
            } else {
              nextSteps = [
                ...current.steps.map(item => (item.status === 'running' ? { ...item, status: 'done' as const } : item)),
                {
                  id,
                  step: payload.step,
                  title: payload.title,
                  detail: payload.detail,
                  phase: payload.phase,
                  todoMeta: payload.todo_meta,
                  status: 'running' as const,
                  action: payload.action,
                },
              ];
            }
            return {
              ...prev,
              [responseId]: {
                ...current,
                steps: nextSteps,
                outputs: { ...current.outputs, [id]: current.outputs[id] || [] },
                activeStepId: existingIdx >= 0 ? id : current.activeStepId || id,
              },
            };
          });
          setActiveMessageId(responseId);
          setRightPanelCollapsed(false);
        } else if (payload.type === 'step.meta') {
          if (payload.action && payload.action.toLowerCase() === 'terminate') {
            terminatedStepIdsRef.current.add(payload.id);
            setExecutionMap(prev => {
              const current = prev[responseId];
              if (!current) return prev;
              return {
                ...prev,
                [responseId]: {
                  ...current,
                  steps: current.steps.filter(item => item.id !== payload.id),
                  activeStepId: current.activeStepId === payload.id ? null : current.activeStepId,
                },
              };
            });
            return;
          }
          if (payload.action) setSelectedStepId(null);
          setExecutionMap(prev => {
            const current = prev[responseId];
            if (!current) return prev;
            const nextSteps = current.steps.map(item => {
              if (item.id !== payload.id) return item;
              const parts: string[] = [];
              if (payload.action) {
                parts.push(`Action: ${payload.action}`);
                if (
                  payload.action !== 'code_interpreter' &&
                  payload.action !== 'shell_interpreter' &&
                  payload.action_input
                ) {
                  const inputStr =
                    typeof payload.action_input === 'string'
                      ? payload.action_input
                      : JSON.stringify(payload.action_input, null, 2);
                  parts.push(`Action Input: ${inputStr}`);
                }
              }
              return {
                ...item,
                title: payload.title || item.title,
                detail: parts.join('\n') || item.detail,
                action: payload.action || item.action,
                actionInput: payload.action_input || item.actionInput,
                todoMeta: payload.todo_meta || item.todoMeta,
              };
            });
            const displayThought = payload.action_intention
              ? payload.action_reason
                ? `${payload.action_intention}\n${payload.action_reason}`
                : payload.action_intention
              : payload.thought;
            const nextThoughts =
              displayThought && !current.stepThoughts?.[payload.id]
                ? { ...current.stepThoughts, [payload.id]: displayThought }
                : current.stepThoughts;
            return {
              ...prev,
              [responseId]: {
                ...current,
                steps: nextSteps,
                stepThoughts: nextThoughts,
                ...(payload.action ? { activeStepId: payload.id } : {}),
              },
            };
          });
        } else if (payload.type === 'step.chunk') {
          const id = payload.id;
          if (terminatedStepIdsRef.current.has(id || '')) return;
          setExecutionMap(prev => {
            const current = prev[responseId];
            if (!current) return prev;
            const targetId = id || current.activeStepId;
            if (!targetId) return prev;
            const list = current.outputs[targetId] ? [...current.outputs[targetId]] : [];
            list.push({ output_type: payload.output_type, content: payload.content });
            return { ...prev, [responseId]: { ...current, outputs: { ...current.outputs, [targetId]: list } } };
          });
        } else if (payload.type === 'step.done') {
          const id = payload.id;
          if (terminatedStepIdsRef.current.has(id || '')) return;
          setExecutionMap(prev => {
            const current = prev[responseId];
            if (!current) return prev;
            const targetId = id || current.activeStepId;
            if (!targetId) return prev;
            return {
              ...prev,
              [responseId]: {
                ...current,
                steps: current.steps.map(item =>
                  item.id === targetId
                    ? {
                        ...item,
                        status: payload.status || 'done',
                        elapsedMs: typeof payload.elapsed_ms === 'number' ? payload.elapsed_ms : item.elapsedMs,
                      }
                    : item,
                ),
              },
            };
          });
        } else if (payload.type === 'step.thought') {
          const content = payload.content || '';
          let normalizedThought = '';
          if (typeof content === 'string') normalizedThought = content;
          else if (content && typeof content === 'object') {
            const todoValue = (content as Record<string, unknown>).TODO;
            if (typeof todoValue === 'string') normalizedThought = todoValue;
            else {
              try {
                normalizedThought = JSON.stringify(content);
              } catch (_e) {
                normalizedThought = String(content);
              }
            }
          }
          if (normalizedThought) {
            setExecutionMap(prev => {
              const current = prev[responseId];
              if (!current) return prev;
              const targetId = payload.id || current.activeStepId || 'initial';
              return {
                ...prev,
                [responseId]: {
                  ...current,
                  stepThoughts: {
                    ...current.stepThoughts,
                    [targetId]: (current.stepThoughts?.[targetId] || '') + normalizedThought,
                  },
                },
              };
            });
          }
        } else if (payload.type === 'final') {
          setExecutionMap(prev => {
            const current = prev[responseId];
            if (!current) return prev;
            return {
              ...prev,
              [responseId]: {
                ...current,
                steps: current.steps.map(item => (item.status === 'running' ? { ...item, status: 'done' } : item)),
              },
            };
          });
          setMessages(prev =>
            prev.map(msg =>
              msg.id === responseId && msg.role === 'view'
                ? { ...msg, context: cleanFinalContent(payload.content || ''), thinking: false }
                : msg,
            ),
          );
          setTaskPlan([]);
          setActiveMessageId(responseId);
          if (payload.content && payload.content.trim()) {
            setStreamingSummary('');
            setSummaryComplete(false);
            const summaryText = cleanFinalContent(payload.content);
            const charsPerFrame = 3;
            const frameInterval = 15;
            let lastTime = 0;
            let currentLen = 0;
            let rafId = 0;
            const animate = (time: number) => {
              if (!lastTime) lastTime = time;
              if (time - lastTime >= frameInterval) {
                lastTime = time;
                currentLen = Math.min(currentLen + charsPerFrame, summaryText.length);
                setStreamingSummary(summaryText.slice(0, currentLen));
                if (currentLen >= summaryText.length) {
                  setSummaryComplete(true);
                  return;
                }
              }
              rafId = requestAnimationFrame(animate);
            };
            rafId = requestAnimationFrame(animate);
          }
        }
      };

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed) processEvent(trimmed);
        }
      }
      if (buffer.trim()) processEvent(buffer.trim());

      fetchConversationList();
    } catch (error: any) {
      if (error.name === 'AbortError') return;
      const errorMessage = error?.message || '请求失败，请稍后重试';
      message.error(errorMessage);
      updateAssistantMessage(responseId, msg => ({ ...msg, context: errorMessage, thinking: false }));
    } finally {
      setLoading(false);
    }
  };

  const displayTitle = useCallback((item: ConversationItem) => item.user_input || item.select_param || '新对话', []);

  const filteredConversationList = useMemo(() => {
    const keyword = historySearch.trim().toLowerCase();
    if (!keyword) return conversationList;
    return conversationList.filter(item => {
      const searchableText = [displayTitle(item), item.conv_uid, item.gmt_created]
        .filter(Boolean)
        .join(' ')
        .toLowerCase();
      return searchableText.includes(keyword);
    });
  }, [conversationList, displayTitle, historySearch]);

  const renderModelOption = (modelName: string, showModelIcon = true) => (
    <span className='flex min-w-0 items-center gap-2'>
      {showModelIcon ? (
        <ModelIcon width={18} height={18} model={modelName} />
      ) : (
        <RobotOutlined style={{ color: '#9ca3af' }} />
      )}
      <span className='truncate'>{modelName}</span>
    </span>
  );

  /* ── rounds (for Manus layout) ── */

  const rounds = useMemo<Round[]>(() => {
    const result: Round[] = [];
    let i = 0;
    while (i < messages.length) {
      const msg = messages[i];
      if (msg.role === 'human') {
        const next = messages[i + 1];
        if (next && next.role === 'view') {
          result.push({ humanMsg: msg, viewMsg: next });
          i += 2;
        } else {
          result.push({ humanMsg: msg, viewMsg: null });
          i += 1;
        }
      } else if (msg.role === 'view') {
        result.push({ humanMsg: null, viewMsg: msg });
        i += 1;
      } else {
        i += 1;
      }
    }
    return result;
  }, [messages]);

  const selectedViewMsgId = useMemo(() => {
    if (activeViewMsgId && rounds.some(r => r.viewMsg?.id === activeViewMsgId)) return activeViewMsgId;
    const lastRound = rounds[rounds.length - 1];
    return lastRound?.viewMsg?.id || null;
  }, [activeViewMsgId, rounds]);

  const artifacts = useMemo(() => {
    if (!selectedViewMsgId) return [];
    const exec = executionMap[selectedViewMsgId];
    if (!exec) return [];
    return buildArtifactsFromExecution(selectedViewMsgId, exec);
  }, [executionMap, selectedViewMsgId]);

  /* ───────── render ───────── */

  return (
    <ConfigProvider theme={{ token: { colorPrimary: '#2563eb', borderRadius: 6 } }}>
      <Head>
        <title>{ASSISTANT_TITLE}</title>
        <link rel='icon' href={BRAND_LOGO} />
        <link rel='apple-touch-icon' href={BRAND_LOGO} />
      </Head>
      <main className='h-screen w-screen overflow-hidden bg-white text-[#111827] dark:bg-[#111111] dark:text-gray-100'>
        <div className='flex h-full'>
          {/* ── Sidebar ── */}
          <aside
            className={`flex flex-col h-screen bg-bar dark:bg-[#232734] transition-all duration-300 ease-in-out ${sidebarOpen ? 'w-[240px] min-w-[240px]' : 'w-14 min-w-[3.5rem]'}`}
          >
            {sidebarOpen ? (
              <div className='flex flex-col h-full px-4 pt-4'>
                <div className='flex items-center justify-between p-2 pb-4'>
                  <div className='flex items-center gap-2'>
                    <img src={BRAND_LOGO} alt='logo' className='h-8 w-8 rounded object-contain' />
                    <span className='text-sm font-semibold text-gray-700 dark:text-gray-200'>{ASSISTANT_TITLE}</span>
                  </div>
                  <Tooltip title='收起侧栏'>
                    <button
                      type='button'
                      aria-label='收起侧栏'
                      onClick={() => setSidebarOpen(false)}
                      className='flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300'
                    >
                      <MenuFoldOutlined style={{ fontSize: 14 }} />
                    </button>
                  </Tooltip>
                </div>
                <button
                  type='button'
                  onClick={handleNewChat}
                  className='mb-4 flex w-full cursor-pointer items-center justify-center gap-2 rounded-xl bg-black px-4 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 dark:bg-white dark:text-black'
                >
                  <PlusOutlined className='text-xs' />
                  <span>新建对话</span>
                </button>
                <div className='mb-3'>
                  <div className='flex h-9 items-center gap-2 rounded-xl bg-[#F1F5F9] px-3 text-gray-400 ring-1 ring-transparent transition-colors focus-within:bg-white focus-within:ring-blue-100 dark:bg-theme-dark dark:focus-within:bg-[#1a1b1e] dark:focus-within:ring-blue-900/40'>
                    <SearchOutlined className='flex-shrink-0 text-xs' />
                    <input
                      aria-label='搜索历史对话'
                      value={historySearch}
                      onChange={e => setHistorySearch(e.target.value)}
                      placeholder='搜索历史对话'
                      className='min-w-0 flex-1 bg-transparent text-xs text-gray-600 outline-none placeholder:text-gray-400 dark:text-gray-200 dark:placeholder:text-gray-500'
                    />
                    {historySearch && (
                      <button
                        type='button'
                        aria-label='清空搜索'
                        onClick={() => setHistorySearch('')}
                        className='flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-600 dark:hover:bg-gray-700 dark:hover:text-gray-300'
                      >
                        <CloseOutlined className='text-[10px]' />
                      </button>
                    )}
                  </div>
                </div>
                <div className='mb-2 mt-4 px-1'>
                  <span className='text-xs font-semibold uppercase tracking-wider text-gray-400'>全部任务</span>
                </div>
                <div className='min-h-0 flex-1 overflow-y-auto'>
                  {listLoading ? (
                    <div className='px-2 pt-2'>
                      <Skeleton active title={false} paragraph={{ rows: 4, width: '100%' }} />
                    </div>
                  ) : filteredConversationList.length > 0 ? (
                    <div className='space-y-0.5'>
                      {filteredConversationList.map(item => (
                        <div
                          key={item.conv_uid}
                          className={`group flex cursor-pointer items-start gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors hover:bg-[#F1F5F9] dark:hover:bg-theme-dark ${conversationId === item.conv_uid ? 'bg-[#F1F5F9] dark:bg-theme-dark' : ''}`}
                          onClick={() => loadConversation(item.conv_uid)}
                        >
                          <MessageOutlined className='mt-1 flex-shrink-0 text-xs text-gray-400' />
                          <div className='min-w-0 flex-1'>
                            <div className='truncate font-medium leading-5 text-gray-700 dark:text-gray-300'>
                              {typeof displayTitle(item) === 'string'
                                ? displayTitle(item).slice(0, 40) || '新对话'
                                : '新对话'}
                            </div>
                            {item.gmt_created && (
                              <div className='mt-0.5 text-[11px] text-gray-400'>
                                {formatRelativeTime(item.gmt_created)}
                              </div>
                            )}
                          </div>
                          <Tooltip title='删除'>
                            <DeleteOutlined
                              onClick={e => handleDeleteConversation(item.conv_uid, e)}
                              className='mt-1 flex-shrink-0 text-gray-300 opacity-0 transition-opacity hover:text-red-500 group-hover:opacity-100'
                            />
                          </Tooltip>
                        </div>
                      ))}
                    </div>
                  ) : conversationList.length > 0 ? (
                    <div className='px-3 py-8 text-center'>
                      <div className='mb-2 text-gray-300 dark:text-gray-600'>
                        <SearchOutlined style={{ fontSize: 24 }} />
                      </div>
                      <p className='text-xs text-gray-400'>未找到匹配对话</p>
                    </div>
                  ) : (
                    <div className='px-3 py-8 text-center'>
                      <div className='mb-2 text-gray-300 dark:text-gray-600'>
                        <MessageOutlined style={{ fontSize: 24 }} />
                      </div>
                      <p className='text-xs text-gray-400'>暂无对话记录</p>
                    </div>
                  )}
                </div>
                <div className='py-4'>
                  <div className='flex items-center justify-around border-t border-dashed border-gray-200 pt-4 dark:border-gray-700'>
                    <div className='text-xs text-gray-400'>中科中涣 · 数据助理</div>
                  </div>
                </div>
              </div>
            ) : (
              <div className='flex h-full flex-col items-center pt-4'>
                <div className='flex flex-col items-center pb-2'>
                  <img src={BRAND_LOGO} alt='logo' className='h-10 w-10 rounded object-contain' />
                  <Tooltip title='展开侧栏' placement='right'>
                    <button
                      type='button'
                      aria-label='展开侧栏'
                      onClick={() => setSidebarOpen(true)}
                      className='mt-2 flex h-7 w-7 cursor-pointer items-center justify-center rounded-md text-gray-400 transition-colors hover:bg-gray-200 hover:text-gray-600 dark:hover:bg-gray-700'
                    >
                      <MenuOutlined style={{ fontSize: 14 }} />
                    </button>
                  </Tooltip>
                </div>
                <Tooltip title='新建对话' placement='right'>
                  <button
                    type='button'
                    aria-label='新建对话'
                    onClick={handleNewChat}
                    className='mt-2 flex h-12 w-12 cursor-pointer items-center justify-center rounded text-xl hover:bg-blue-50/50 dark:hover:bg-blue-900/10'
                  >
                    <PlusOutlined />
                  </button>
                </Tooltip>
              </div>
            )}
          </aside>

          {/* ── Main content ── */}
          <div className='flex min-w-0 flex-1 flex-col'>
            <header className='flex h-12 flex-shrink-0 items-center gap-2 border-b border-gray-100 px-4 dark:border-[#2a2a2a]'>
              {conversationId && (
                <span className='truncate text-sm text-gray-500'>
                  {conversationList.find(c => c.conv_uid === conversationId)
                    ? displayTitle(conversationList.find(c => c.conv_uid === conversationId)!)
                    : ''}
                </span>
              )}
            </header>

            {messages.length === 0 ? (
              /* ── Empty state with input ── */
              <div className='flex-1 flex flex-col'>
                <section className='min-h-0 flex-1 overflow-y-auto px-4 pt-8'>
                  <div className='mx-auto flex min-h-full w-full max-w-3xl flex-col pb-4'>
                    <div className='flex flex-1 items-center justify-center'>
                      <div className='w-full text-center'>
                        <div className='mx-auto mb-7 flex h-24 w-24 items-center justify-center rounded-3xl bg-white shadow-sm dark:bg-[#181818]'>
                          <img src={BRAND_LOGO} alt='中涣信息' className='h-20 w-20 object-contain' />
                        </div>
                        <div className='text-3xl font-semibold leading-tight text-[#1f2937] dark:text-gray-100'>
                          {ASSISTANT_TITLE}
                        </div>
                        <div className='mx-auto mt-3 max-w-lg text-sm leading-6 text-gray-500 dark:text-gray-400'>
                          直接输入问题，系统将基于连云港快照数据，完成查询、分析和回答
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
                {/* Input area for empty state */}
                <div className='flex-shrink-0 bg-gradient-to-t from-white via-white to-white/85 px-4 pb-5 pt-4 dark:from-[#111111] dark:via-[#111111] dark:to-[#111111]/85'>
                  <div className='mx-auto w-full max-w-3xl'>
                    <ChatInputBox
                      query={query}
                      onQueryChange={setQuery}
                      onSend={handleStart}
                      loading={loading}
                      canSend={canSend}
                      isZhInput={isZhInput}
                      setIsZhInput={setIsZhInput}
                      model={model}
                      modelList={modelList}
                      onModelChange={setModel}
                      renderModelOption={renderModelOption}
                    />
                  </div>
                </div>
              </div>
            ) : (
              /* ── Manus left/right layout ── */
              <div className='flex-1 flex overflow-hidden'>
                {/* Left panel */}
                <div
                  className={`${rightPanelCollapsed ? 'flex-1 max-w-[800px] border-r-0' : 'flex-[2] min-w-0 border-r border-gray-200/80 dark:border-gray-800'} flex flex-col overflow-hidden bg-white dark:bg-[#111217] transition-all duration-300 relative`}
                >
                  <div className='flex-1 min-h-0 overflow-y-auto'>
                    {rounds.map((round, roundIndex) => {
                      const isLastRound = roundIndex === rounds.length - 1;
                      const isSelected = round.viewMsg?.id === selectedViewMsgId;
                      const execution = round.viewMsg?.id ? executionMap[round.viewMsg.id] : undefined;
                      const { sections, stepThoughts } = convertToManusFormat(execution, t);
                      const isWorking =
                        (isLastRound &&
                          (round.viewMsg?.thinking || execution?.steps.some(s => s.status === 'running') || false)) ||
                        false;
                      const roundAssistantText = isLastRound
                        ? streamingSummary || round.viewMsg?.context || undefined
                        : round.viewMsg?.context || undefined;
                      const roundArtifacts =
                        round.viewMsg?.id && execution ? buildArtifactsFromExecution(round.viewMsg.id, execution) : [];

                      return (
                        <ManusLeftPanel
                          key={round.viewMsg?.id || round.humanMsg?.id || `round-${roundIndex}`}
                          sections={sections}
                          activeStepId={isSelected ? selectedStepId || execution?.activeStepId : undefined}
                          onStepClick={stepId => {
                            if (round.viewMsg?.id) {
                              setActiveViewMsgId(round.viewMsg.id);
                              setSelectedStepId(stepId);
                              setRightPanelCollapsed(false);
                              setExecutionMap(prev => ({
                                ...prev,
                                [round.viewMsg!.id!]: { ...prev[round.viewMsg!.id!], activeStepId: stepId },
                              }));
                            }
                          }}
                          isWorking={isWorking}
                          userQuery={round.humanMsg?.context}
                          assistantText={roundAssistantText}
                          modelName={round.viewMsg?.model_name || model}
                          stepThoughts={stepThoughts}
                          artifacts={roundArtifacts}
                          onArtifactClick={artifact => {
                            if (round.viewMsg?.id) setActiveViewMsgId(round.viewMsg.id);
                            if (artifact.type === 'html') setRightPanelView('html-preview');
                            else if (artifact.type === 'image') setRightPanelView('image-preview');
                            else downloadArtifact(artifact);
                            setRightPanelCollapsed(false);
                          }}
                          taskPlan={round.viewMsg?.taskPlan}
                          isCollapsed={!isLastRound && !isSelected}
                          onExpand={() => {
                            if (round.viewMsg?.id) setActiveViewMsgId(round.viewMsg.id);
                          }}
                          onResend={round.humanMsg?.context ? () => handleStart(round.humanMsg!.context) : undefined}
                          resendDisabled={loading}
                        />
                      );
                    })}
                    <div ref={messagesEndRef} />
                  </div>

                  {/* Input area */}
                  <div className='bg-gradient-to-t from-white via-white/95 to-white/80 dark:from-[#1a1b1e] dark:via-[#1a1b1e]/95 dark:to-[#1a1b1e]/80 p-4 md:p-6 pt-2'>
                    <div className='max-w-[720px] mx-auto'>
                      <ChatInputBox
                        query={query}
                        onQueryChange={setQuery}
                        onSend={handleStart}
                        loading={loading}
                        canSend={canSend}
                        isZhInput={isZhInput}
                        setIsZhInput={setIsZhInput}
                        model={model}
                        modelList={modelList}
                        onModelChange={setModel}
                        renderModelOption={renderModelOption}
                      />
                    </div>
                  </div>
                </div>

                {/* Panel toggle */}
                <div className='relative z-20 flex-shrink-0'>
                  <Tooltip title={rightPanelCollapsed ? '展开面板' : '收起面板'} placement='left'>
                    <button
                      onClick={() => setRightPanelCollapsed(prev => !prev)}
                      className='absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-8 flex items-center justify-center bg-white dark:bg-[#1a1b1e] border border-gray-200 dark:border-gray-700 rounded-full shadow-sm hover:bg-gray-100 dark:hover:bg-gray-800 hover:w-5 hover:shadow-md transition-all duration-200 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'
                    >
                      {rightPanelCollapsed ? (
                        <LeftOutlined style={{ fontSize: 10 }} />
                      ) : (
                        <RightOutlined style={{ fontSize: 10 }} />
                      )}
                    </button>
                  </Tooltip>
                </div>

                {/* Right panel */}
                <div
                  className={`${rightPanelCollapsed ? 'w-0 min-w-0 overflow-hidden opacity-0' : 'flex-[3] min-w-0 overflow-hidden'} bg-[#f8f8fb] dark:bg-[#0f1114] flex flex-col transition-all duration-300`}
                >
                  {(() => {
                    const activeViewMsg = messages.find(m => m.id === selectedViewMsgId && m.role === 'view');
                    const rawExecution = activeViewMsg?.id ? executionMap[activeViewMsg.id] : undefined;
                    const execution =
                      rawExecution && selectedStepId ? { ...rawExecution, activeStepId: selectedStepId } : rawExecution;
                    const { activeStep, outputs, stepThoughts: _stepThoughts } = convertToManusFormat(execution, t);
                    const isRunning = execution?.steps.some(s => s.status === 'running') || false;
                    const rightOutputs: ManusExecutionOutput[] = outputs.map(o => ({ ...o, timestamp: Date.now() }));
                    const activeRound = rounds.find(round => round.viewMsg?.id === selectedViewMsgId);

                    return (
                      <ManusRightPanel
                        activeStep={activeStep}
                        outputs={rightOutputs}
                        isRunning={isRunning}
                        onRerun={
                          activeRound?.humanMsg?.context && !loading
                            ? () => handleStart(activeRound.humanMsg!.context)
                            : undefined
                        }
                        onShare={conversationId ? handleShareConversation : undefined}
                        onCollapse={() => setRightPanelCollapsed(true)}
                        terminalTitle='中涣信息计算机'
                        artifacts={artifacts}
                        onArtifactClick={artifact => {
                          if (artifact.type === 'html') {
                            setRightPanelView('html-preview');
                          } else if (artifact.type === 'image') {
                            setRightPanelView('image-preview');
                          } else {
                            downloadArtifact(artifact);
                          }
                        }}
                        panelView={rightPanelView}
                        onPanelViewChange={setRightPanelView}
                        summaryContent={streamingSummary || activeViewMsg?.context || ''}
                        isSummaryStreaming={!summaryComplete && !!streamingSummary}
                        previewArtifact={
                          rightPanelView === 'html-preview'
                            ? artifacts.find(a => a.type === 'html') || null
                            : rightPanelView === 'image-preview'
                              ? artifacts.find(a => a.type === 'image') || null
                              : null
                        }
                      />
                    );
                  })()}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </ConfigProvider>
  );
};

export default ZhonghuanAssistant;
