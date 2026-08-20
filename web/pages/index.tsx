import { ChatContext } from '@/app/chat-context';
import ModelSelector from '@/components/chat/header/model-selector';
import { useConnectors } from '@/hooks/use-connector-api';
import { buildSubAgentArtifacts, parseSubAgentEvent, restoreSubAgentStates } from '@/hooks/use-subagent-stream';
import {
  ATTACHMENT_PREVIEW_DRAWER_STYLES,
  AttachmentPreview,
  AttachmentPreviewCloseButton,
  AttachmentPreviewPanelTitle,
  AttachmentRail,
  AttachmentRailAddButton,
  AttachmentRailCompactAddButton,
  DEFAULT_UPLOAD_CAPABILITIES,
  PREVIEW_DESKTOP_MIN_WIDTH,
  PREVIEW_DRAWER_MAX_WIDTH,
  extInfoForSend,
  previewFile as previewSessionFile,
  sessionFilesApi,
  snapshotsForSend,
  snapshotsFromInputFiles,
  useSessionFiles,
  type LegacyServerFile,
  type RailItem,
  type RailPreviewState,
  type SessionFileSnapshot,
  type SessionFilesSendSnapshot,
} from '@/modules/session-files';
import { PreprocessingResult } from '@/new-components/analysis';
import { ChartConfig, ChartType } from '@/new-components/charts';
import ContextUsageBar from '@/new-components/chat/content/ContextUsageBar';
import ManusLeftPanel, {
  ExecutionStep as ManusExecutionStep,
  StepType,
  ThinkingSection,
} from '@/new-components/chat/content/ManusLeftPanel';
import ManusRightPanel, {
  ActiveStepInfo,
  ExecutionOutput as ManusExecutionOutput,
  PanelView,
} from '@/new-components/chat/content/ManusRightPanel';
import { MessagePart, ToolPart, ToolStatus } from '@/new-components/chat/content/OpenCodeSessionTurn';
import QuestionDock from '@/new-components/chat/content/QuestionDock';
import SubAgentSection from '@/new-components/chat/content/SubAgentSection';
import TaskPlanCard, { TaskItem } from '@/new-components/chat/content/TaskPlanCard';
import ConfirmDialog from '@/new-components/connector/ConfirmDialog';
import { AttachedConnector, ConnectorInstance } from '@/new-components/connector/types';
import { useConfirmPolling } from '@/new-components/connector/useConfirmPolling';
import FromTaskBanner from '@/new-components/scheduled-task/FromTaskBanner';
import SaveAsScheduledTaskDrawer from '@/new-components/scheduled-task/SaveAsScheduledTaskDrawer';
import type { ChatReplayPayload } from '@/types/scheduled-task';
import type { SubAgentState } from '@/types/subagent';
import { buildActionDisplayText } from '@/utils/action-display';
import axios from '@/utils/ctx-axios';
import { createSummaryPresentation, type SummaryPresentation } from '@/utils/final-presentation';
import { decodeFinalEvent, decodeHistoryAnswer, type AgentCitation } from '@/utils/react-agent-final';
import { sendGetRequest, sendSpacePostRequest } from '@/utils/request';
import {
  ApiOutlined,
  ArrowUpOutlined,
  AudioOutlined,
  BarChartOutlined,
  BellOutlined,
  BookOutlined,
  CheckCircleFilled,
  CloudServerOutlined,
  CodeOutlined,
  ConsoleSqlOutlined,
  DatabaseOutlined,
  DownloadOutlined,
  FileExcelOutlined,
  FileImageOutlined,
  FileOutlined,
  FilePptOutlined,
  FileTextOutlined,
  LeftOutlined,
  PaperClipOutlined,
  PieChartOutlined,
  PlusOutlined,
  ReadOutlined,
  RightOutlined,
  SearchOutlined,
  TableOutlined,
  ThunderboltOutlined,
  UploadOutlined,
  UserOutlined,
} from '@ant-design/icons';
import { useRequest } from 'ahooks';
import {
  Alert,
  Avatar,
  Button,
  ConfigProvider,
  Drawer,
  Dropdown,
  Input,
  List,
  Modal,
  Popover,
  Spin,
  Tag,
  Tooltip,
  Upload,
  message,
} from 'antd';
import { NextPage } from 'next';
import Image from 'next/image';
import { useRouter } from 'next/router';
import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

const cleanFinalContent = (text: string): string => {
  let cleaned = text.replace(/\\n/g, '\n').trim();
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
  cleaned = cleaned.replace(/"\s*\}\s*$/, '').trim();
  // Strip raw ReAct prefixes that may leak from the backend
  cleaned = cleaned.replace(/^(Thought|Action|Action Input|Observation|Phase):\s*/gm, '').trim();
  return cleaned;
};

const _formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
};

const _getFileTypeLabel = (fileName: string, mimeType?: string): string => {
  const ext = fileName.toLowerCase().split('.').pop() || '';
  if (['xlsx', 'xls'].includes(ext) || mimeType?.includes('spreadsheet') || mimeType?.includes('excel')) {
    return '电子表格';
  }
  if (ext === 'csv' || mimeType?.includes('csv')) {
    return '电子表格';
  }
  if (ext === 'pdf' || mimeType?.includes('pdf')) return 'PDF';
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) || mimeType?.includes('image')) return '图片';
  if (['doc', 'docx'].includes(ext) || mimeType?.includes('word')) return 'Word 文档';
  if (['txt', 'md'].includes(ext) || mimeType?.includes('text')) return '文本文件';
  if (['json'].includes(ext)) return 'JSON';
  return '文件';
};

const _getFileIcon = (fileName: string, mimeType?: string) => {
  const ext = fileName.toLowerCase().split('.').pop() || '';
  if (
    ['xlsx', 'xls', 'csv'].includes(ext) ||
    mimeType?.includes('spreadsheet') ||
    mimeType?.includes('excel') ||
    mimeType?.includes('csv')
  ) {
    return <FileExcelOutlined className='text-green-600 text-lg' />;
  }
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext) || mimeType?.includes('image')) {
    return <FileImageOutlined className='text-pink-500 text-lg' />;
  }
  if (['ppt', 'pptx'].includes(ext)) {
    return <FilePptOutlined className='text-orange-500 text-lg' />;
  }
  return <FileTextOutlined className='text-blue-500 text-lg' />;
};

interface DataSource {
  id: number;
  type: string;
  params: Record<string, any>;
  description?: string;
  db_name: string; // derived from params.name
  db_type: string; // alias for type
  gmt_created?: string;
  gmt_modified?: string;
}

// Define Knowledge Base Interface (Partial)
interface KnowledgeSpace {
  id: number;
  name: string;
  vector_type: string;
  desc?: string;
  owner?: string;
}

// Define message type for chat
interface ChatMessage {
  id?: string;
  role: 'human' | 'view';
  context: string;
  model_name?: string;
  order?: number;
  thinking?: boolean;
  /** Immutable server snapshots of every session file attached to this message. */
  attachedFiles?: readonly SessionFileSnapshot[];
  attachedKnowledge?: KnowledgeSpace;
  attachedSkill?: { name: string; id: string };
  attachedDb?: { db_name: string; db_type: string };
  taskPlan?: TaskItem[];
  attachedConnectors?: AttachedConnector[];
  citations?: AgentCitation[];
}

interface ExecutionStep {
  id: string;
  step: number;
  title?: string;
  detail: string;
  status: 'running' | 'done' | 'failed';
  action?: string;
  actionInput?: any;
  todoMeta?: {
    state?: 'init' | 'progress' | 'done';
    done?: number;
    total?: number;
  };
}

interface ExecutionOutput {
  output_type: string;
  content: any;
}

interface Skill {
  id: string;
  name: string;
  description: string;
  type: 'official' | 'personal';
  icon?: string;
}

type ArtifactType = 'file' | 'table' | 'chart' | 'image' | 'code' | 'markdown' | 'summary' | 'html';

interface Artifact {
  id: string;
  type: ArtifactType;
  name: string;
  content: any;
  createdAt: number;
  messageId?: string;
  stepId?: string;
  downloadable?: boolean;
  mimeType?: string;
  size?: number;
  filePath?: string;
  /** Which sub-agent produced this artifact (for sub-agent produced files). */
  sourceAgent?: string;
  // Chart-specific metadata
  chartType?: ChartType;
  chartConfig?: Partial<ChartConfig>;
}

type RightPanelTab = 'preview' | 'files' | 'charts' | 'tables' | 'analysis' | 'preprocess' | 'summary';

const _convertExecutionToMessageParts = (
  execution:
    | {
        steps: ExecutionStep[];
        outputs: Record<string, ExecutionOutput[]>;
        activeStepId: string | null;
        collapsed: boolean;
      }
    | undefined,
): MessagePart[] => {
  if (!execution || !execution.steps.length) return [];

  return execution.steps.map((step): ToolPart => {
    const outputs = execution.outputs[step.id] || [];
    const outputText = outputs
      .map(o => {
        if (o.output_type === 'text' || o.output_type === 'markdown') {
          return String(o.content);
        }
        if (o.output_type === 'code') {
          return `\`\`\`\n${String(o.content)}\n\`\`\``;
        }
        if (o.output_type === 'table' || o.output_type === 'json') {
          return JSON.stringify(o.content, null, 2);
        }
        if (o.output_type === 'html') {
          return '[HTML Report]';
        }
        return String(o.content);
      })
      .filter(Boolean)
      .join('\n');

    const statusMap: Record<string, ToolStatus> = {
      running: 'running',
      done: 'completed',
      failed: 'error',
    };

    const actionLower = (step.action || '').toLowerCase();
    const isSkill =
      actionLower.includes('skill') ||
      actionLower === 'execute_skill_script_file' ||
      actionLower === 'get_skill_resource' ||
      actionLower === 'select_skill' ||
      actionLower === 'load_skill';
    const toolName = isSkill
      ? 'skill'
      : step.title?.toLowerCase().includes('skill')
        ? 'skill'
        : step.title?.toLowerCase().includes('read')
          ? 'read'
          : step.title?.toLowerCase().includes('write')
            ? 'write'
            : step.title?.toLowerCase().includes('code') ||
                step.title?.toLowerCase().includes('execute') ||
                actionLower === 'shell_interpreter'
              ? 'bash'
              : 'task';

    return {
      id: step.id,
      type: 'tool',
      tool: toolName,
      state: {
        status: statusMap[step.status] || 'completed',
        input: { description: step.title || 'Step', detail: step.detail },
        output: outputText || step.detail,
      },
    };
  });
};

// Convert execution data to Manus panel format
const convertToManusFormat = (
  execution:
    | {
        steps: ExecutionStep[];
        outputs: Record<string, ExecutionOutput[]>;
        activeStepId: string | null;
        collapsed: boolean;
        stepThoughts?: Record<string, string>;
      }
    | undefined,
  _userQuery?: string,
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

  // Determine step type from title
  const getStepType = (title?: string, action?: string): StepType => {
    // Check action name first — it's the most reliable indicator
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
    if (actionLower === 'question') return 'question';
    if (
      actionLower === 'kb_ls' ||
      actionLower === 'kb_glob' ||
      actionLower === 'kb_grep' ||
      actionLower === 'kb_cat' ||
      actionLower === 'semantic_search'
    )
      return 'kb';
    if (
      actionLower === 'kb_codegraph_explore' ||
      actionLower === 'kb_codegraph_call_chain' ||
      actionLower === 'kb_codegraph_class_hierarchy'
    )
      return 'code_graph';

    const lower = (title || '').toLowerCase();
    if (
      lower.includes('load_skill') ||
      lower.includes('load skill') ||
      lower.includes('execute_skill_script_file') ||
      lower.includes('get_skill_resource') ||
      lower.includes('select_skill')
    )
      return 'skill';
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
    if (lower.includes('question')) return 'question';
    if (lower.includes('skill')) return 'skill';
    if (lower.includes('task')) return 'task';
    return 'other';
  };

  // Get step status mapping
  const getStepStatus = (status: string): 'pending' | 'running' | 'completed' | 'error' => {
    if (status === 'running') return 'running';
    if (status === 'done') return 'completed';
    if (status === 'failed') return 'error';
    return 'pending';
  };

  // Group steps into sections (for now, create one section with all steps)
  // In a more advanced version, you could group by phase/category
  const steps: ManusExecutionStep[] = execution.steps
    .filter(step => {
      const detail = (step.detail || '').toLowerCase();
      return !detail.includes('action: terminate');
    })
    .map(step => {
      const cleanDetail = step.detail?.replace(/^Thought:.*\n?/gm, '').trim();
      // Build a user-friendly subtitle: strip "Action: " prefix from the first line
      const firstLine = cleanDetail?.split('\n')[0] || '';
      const friendlySubtitle = firstLine.replace(/^Action:\s*/i, '').slice(0, 80);
      return {
        id: step.id,
        type: getStepType(step.title, step.action),
        title: step.title || `Step ${step.step}`,
        subtitle: friendlySubtitle || undefined,
        description: cleanDetail || undefined,
        phase: (step as any).phase,
        status: getStepStatus(step.status),
        action: step.action,
        actionInput: step.actionInput,
      };
    });

  const sections: ThinkingSection[] = [
    {
      id: 'section-execution',
      title: t ? t('execution_steps') : 'Execution Steps',
      isCompleted: steps.every(s => s.status === 'completed'),
      steps,
    },
  ];

  // Get active step info
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
      };
    }
  }

  // Get outputs for active step
  const outputs: ManusExecutionOutput[] = execution.activeStepId
    ? (execution.outputs[execution.activeStepId] || []).map(o => ({
        output_type: o.output_type as any,
        content: o.content,
        timestamp: Date.now(),
      }))
    : [];

  const stepThoughts = { ...(execution.stepThoughts || {}) };
  execution.steps.forEach(step => {
    if (step.action === 'dispatch_parallel_tasks') {
      delete stepThoughts[step.id];
    }
  });

  return { sections, activeStep, outputs, stepThoughts };
};

const EXAMPLE_CARDS = [
  {
    id: 'walmart_sales',
    icon: '📊',
    title: '沃尔玛销售数据分析',
    description: '分析沃尔玛销售CSV数据，生成可视化网页报告',
    query:
      '请全面分析这份沃尔玛销售数据，包括各门店销售趋势、假日影响、温度与油价对销售的影响等维度，生成一份精美的交互式网页分析报告。',
    fileName: 'Walmart_Sales.csv',
    fileType: 'text/csv',
    fileSize: 98304, // ~96 KB
    color: 'from-blue-500/10 to-cyan-500/10',
    borderColor: 'border-blue-200/60 dark:border-blue-800/40',
    iconBg: 'bg-blue-100 dark:bg-blue-900/40',
    skillName: 'csv-data-analysis',
  },
  {
    id: 'db_profile_report',
    icon: '🗄️',
    title: '数据库画像与分析报告',
    description: '连接数据库后，生成数据库画像并生成可视化网页报告',
    query:
      '请分析当前连接的数据库，生成数据库画像（包括表结构、字段信息、数据量统计等），并生成一份精美的交互式网页分析报告。',
    dbName: 'Walmart_Sales',
    color: 'from-emerald-500/10 to-teal-500/10',
    borderColor: 'border-emerald-200/60 dark:border-emerald-800/40',
    iconBg: 'bg-emerald-100 dark:bg-emerald-900/40',
  },
  {
    id: 'fin_report',
    icon: '📈',
    title: '金融财报深度分析',
    description: '分析浙江海翔药业年度报告，生成数据可视化报告',
    query:
      '请深度分析这份浙江海翔药业2019年年度报告，包括营收利润趋势、资产负债结构、现金流分析、关键财务指标等，生成一份专业的交互式网页分析报告。',
    fileName: '2020-01-23__浙江海翔药业股份有限公司__002099__海翔药业__2019年__年度报告.pdf',
    fileType: 'application/pdf',
    fileSize: 2621440, // ~2.5 MB
    color: 'from-violet-500/10 to-purple-500/10',
    borderColor: 'border-violet-200/60 dark:border-violet-800/40',
    iconBg: 'bg-violet-100 dark:bg-violet-900/40',
    skillName: 'financial-report-analyzer',
  },
  {
    id: 'create_sql_skill',
    icon: '🛠️',
    title: '创建SQL分析技能',
    description: '使用skill-creator创建一个实用的SQL数据分析技能',
    query:
      '请使用 skill-creator 帮我创建一个实用的SQL数据分析技能，包含连接数据库、执行SQL查询和数据可视化等核心功能。',
    color: 'from-amber-500/10 to-orange-500/10',
    borderColor: 'border-amber-200/60 dark:border-amber-800/40',
    iconBg: 'bg-amber-100 dark:bg-amber-900/40',
    skillName: 'skill-creator',
  },
];

const Playground: NextPage = () => {
  const router = useRouter();
  const { t } = useTranslation();
  const { model, setModel } = useContext(ChatContext);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const exampleRunInFlightRef = useRef(false);
  const sendInFlightRef = useRef(false);

  // Selection State
  const [isDbModalOpen, setIsDbModalOpen] = useState(false);
  const [isKnowledgeModalOpen, setIsKnowledgeModalOpen] = useState(false);

  // Contexts
  const [selectedDb, setSelectedDb] = useState<DataSource | null>(null);
  const [selectedKnowledge, setSelectedKnowledge] = useState<KnowledgeSpace | null>(null);
  // Chat messages state
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // --- Session files (Task12): rail drafts + send snapshots ---------------
  const sessionFiles = useSessionFiles({ api: sessionFilesApi });
  const hasSessionFileDrafts = sessionFiles.files.length > 0;
  // Legacy example file staged in the rail (legacy file_path protocol).
  const hasLegacyFile = !!sessionFiles.legacyFile;
  // Ref mirror so pick/send callbacks always read the latest conversation id.
  const conversationIdRef = useRef<string | null>(null);
  conversationIdRef.current = conversationId;

  // Composer attachment preview state; desktop renders inside the right
  // panel, smaller viewports use the rail's own overlay Drawer.
  const [sessionFilePreview, setSessionFilePreview] = useState<RailPreviewState | null>(null);
  const sessionFilePreviewRequestRef = useRef(0);
  const [queuedSendAfterUpload, setQueuedSendAfterUpload] = useState(false);
  const [viewportWidth, setViewportWidth] = useState<number>(() =>
    typeof window === 'undefined' ? PREVIEW_DESKTOP_MIN_WIDTH : window.innerWidth,
  );
  useEffect(() => {
    const onResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  const isDesktopWidth = viewportWidth >= PREVIEW_DESKTOP_MIN_WIDTH;
  // Desktop + chat view swaps the right panel content for the preview, so the
  // rail must not open its own Drawer (its overlay already hides ≥1024px).
  const showInlineAttachmentPreview = isDesktopWidth && !!sessionFilePreview && messages.length > 0;

  const ensureSessionFilesConvId = useCallback((): string => {
    const existing = conversationIdRef.current;
    if (existing) return existing;
    const next = generateUUID();
    conversationIdRef.current = next;
    setConversationId(next);
    return next;
  }, []);

  const openSessionFilePreview = useCallback(async (item: RailItem) => {
    const convId = conversationIdRef.current;
    if (!convId || !item.fileId) return;
    const requestVersion = ++sessionFilePreviewRequestRef.current;
    // Desktop previews render inside the right panel: make sure it is visible.
    setRightPanelCollapsed(false);
    setSessionFilePreview({ snapshot: null, loading: true, error: null, size: item.size });
    try {
      const previewSnapshot = await previewSessionFile(convId, item.fileId);
      if (requestVersion !== sessionFilePreviewRequestRef.current) return;
      setSessionFilePreview({ snapshot: previewSnapshot, loading: false, error: null, size: item.size });
    } catch (err: any) {
      if (requestVersion !== sessionFilePreviewRequestRef.current) return;
      setSessionFilePreview({
        snapshot: null,
        loading: false,
        error: err?.message || 'Preview failed',
        size: item.size,
      });
    }
  }, []);

  const closeSessionFilePreview = useCallback(() => {
    sessionFilePreviewRequestRef.current += 1;
    setSessionFilePreview(null);
  }, []);

  // Ant Drawer handles Escape itself. The desktop in-chat preview is an
  // inline panel, so mirror the same keyboard interaction there.
  useEffect(() => {
    if (!showInlineAttachmentPreview) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      closeSessionFilePreview();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [closeSessionFilePreview, showInlineAttachmentPreview]);

  // Drag & drop is scoped to the composer: the hover overlay and the upload
  // live on the composer containers (see composerDragHandlers below). These
  // window handlers only swallow the browser default so that dropping a file
  // anywhere outside the composer never navigates away to the file.
  useEffect(() => {
    const swallow = (e: DragEvent) => {
      if (!e.dataTransfer?.types?.includes('Files')) return;
      e.preventDefault();
    };
    window.addEventListener('dragover', swallow);
    window.addEventListener('drop', swallow);
    return () => {
      window.removeEventListener('dragover', swallow);
      window.removeEventListener('drop', swallow);
    };
  }, []);

  // Composer-scoped drag & drop ("拖拽悬停态"): hovering a file drag over the
  // composer shows the dashed overlay (only while hovering, never persistent);
  // dropping there uploads into the draft rail. A depth counter absorbs the
  // enter/leave pairs fired when moving between child elements.
  const [isFileDragActive, setIsFileDragActive] = useState(false);
  const fileDragDepthRef = useRef(0);
  const dragEventHasFiles = (e: React.DragEvent) => e.dataTransfer?.types?.includes('Files') ?? false;
  const composerDragHandlers = {
    onDragEnter: (e: React.DragEvent) => {
      if (!dragEventHasFiles(e)) return;
      e.preventDefault();
      fileDragDepthRef.current += 1;
      setIsFileDragActive(true);
    },
    // Required so the browser fires `drop` instead of navigating away.
    onDragOver: (e: React.DragEvent) => {
      if (!dragEventHasFiles(e)) return;
      e.preventDefault();
    },
    onDragLeave: (e: React.DragEvent) => {
      if (!dragEventHasFiles(e)) return;
      fileDragDepthRef.current = Math.max(0, fileDragDepthRef.current - 1);
      if (fileDragDepthRef.current === 0) setIsFileDragActive(false);
    },
    onDrop: (e: React.DragEvent) => {
      if (!dragEventHasFiles(e)) return;
      e.preventDefault();
      // Keep the window-level swallow handler from seeing this drop twice.
      e.stopPropagation();
      fileDragDepthRef.current = 0;
      setIsFileDragActive(false);
      const files = e.dataTransfer?.files;
      if (!files || files.length === 0) return;
      void sessionFiles.addFiles(Array.from(files), ensureSessionFilesConvId());
    },
  };

  // Extension list for the drag overlay subtitle, driven by server
  // capabilities with the same fallback used for validation.
  const supportedDragFormats = useMemo(() => {
    const exts = sessionFiles.capabilities?.supported_extensions ?? DEFAULT_UPLOAD_CAPABILITIES.supported_extensions;
    return exts.map(ext => ext.replace(/^\./, '')).join(' · ');
  }, [sessionFiles.capabilities]);

  // Overlay rendered inside the composer container while isFileDragActive.
  // pointer-events-none keeps it visual-only: the composer container's own
  // handlers above own drag bookkeeping and the drop.
  const composerDragOverlay = isFileDragActive ? (
    <div className='pointer-events-none absolute inset-0 z-30 flex p-2'>
      <div className='flex flex-1 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-blue-400 bg-blue-50/95 dark:border-blue-500 dark:bg-[#111217]/95'>
        <div className='flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500 shadow-lg shadow-blue-500/30'>
          <DownloadOutlined className='text-lg text-white' />
        </div>
        <div className='text-sm font-semibold text-blue-600 dark:text-blue-400'>{t('release_to_add_files')}</div>
        <div className='max-w-sm px-3 text-center text-xs text-gray-400 dark:text-gray-500'>
          {t('supported_file_formats')} {supportedDragFormats}
        </div>
      </div>
    </div>
  ) : null;

  // Legacy server-preloaded example file: fetch bounded content and render it
  // through the same preview surfaces (Drawer/desktop right panel).
  const openLegacyFilePreview = useCallback(
    async (file: { name: string; size: number; media_type: string; file_path: string }) => {
      const requestVersion = ++sessionFilePreviewRequestRef.current;
      setRightPanelCollapsed(false);
      setSessionFilePreview({ snapshot: null, loading: true, error: null, size: file.size });
      try {
        const [data] = await sendGetRequest('/api/v1/resource/file/read', { file_key: file.file_path });
        const content: string = typeof data?.content === 'string' ? data.content : '';
        const ext = file.name.toLowerCase().split('.').pop() ?? '';
        const TABLE_EXTS = new Set(['csv']);
        const byteTruncated = content.length > 1024 * 1024;
        const text = byteTruncated ? content.slice(0, 1024 * 1024) : content;
        let truncated = byteTruncated;
        let preview: Record<string, unknown>;
        let kind: string;
        if (TABLE_EXTS.has(ext)) {
          kind = 'table';
          const availableLines = text.split(/\r?\n/).filter(line => line.length > 0);
          truncated = truncated || availableLines.length > 101;
          const lines = availableLines.slice(0, 101);
          const rows = lines.map(line => line.split(','));
          preview = { encoding: 'utf-8', delimiter: ',', rows };
        } else {
          kind = 'text';
          preview = { encoding: 'utf-8', text };
        }
        if (requestVersion !== sessionFilePreviewRequestRef.current) return;
        setSessionFilePreview({
          snapshot: {
            file_id: `legacy:${file.name}`,
            name: file.name,
            media_type: file.media_type,
            kind,
            status: 'ready',
            truncated,
            preview,
          },
          loading: false,
          error: null,
          size: file.size,
        });
      } catch (err: any) {
        if (requestVersion !== sessionFilePreviewRequestRef.current) return;
        setSessionFilePreview({
          snapshot: null,
          loading: false,
          error: err?.message || 'Preview failed',
          size: file.size,
        });
      }
    },
    [],
  );

  const renderSessionFilePreviewBody = () => {
    if (!sessionFilePreview) return null;
    if (sessionFilePreview.loading) {
      return (
        <div className='flex h-40 items-center justify-center'>
          <Spin />
        </div>
      );
    }
    if (sessionFilePreview.error) {
      return <Alert type='error' showIcon message='预览失败' description={sessionFilePreview.error} />;
    }
    return <AttachmentPreview snapshot={sessionFilePreview.snapshot} size={sessionFilePreview.size} />;
  };

  const clearComposerAttachments = useCallback(() => {
    sessionFiles.clearTurn();
    closeSessionFilePreview();
    setQueuedSendAfterUpload(false);
  }, [closeSessionFilePreview, sessionFiles]);

  const [executionMap, setExecutionMap] = useState<
    Record<
      string,
      {
        steps: ExecutionStep[];
        outputs: Record<string, ExecutionOutput[]>;
        activeStepId: string | null;
        collapsed: boolean;
        stepThoughts: Record<string, string>;
        subAgents?: Record<string, SubAgentState>;
        subAgentArtifacts?: number;
      }
    >
  >({});
  const [_activeMessageId, setActiveMessageId] = useState<string | null>(null);

  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [createdSkillNames, setCreatedSkillNames] = useState<Record<string, string>>({});
  const [_rightPanelTab, setRightPanelTab] = useState<RightPanelTab>('preview');
  const [streamingSummary, setStreamingSummary] = useState<string>('');
  const [_summaryComplete, setSummaryComplete] = useState(false);
  const [_showProfessionalReport, _setShowProfessionalReport] = useState(false);
  const [_preprocessedData, _setPreprocessedData] = useState<PreprocessingResult | null>(null);

  const [isSkillPanelOpen, setIsSkillPanelOpen] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [skillSearchQuery, setSkillSearchQuery] = useState('');

  const [isKnowledgePanelOpen, setIsKnowledgePanelOpen] = useState(false);
  const [knowledgeSearchQuery, setKnowledgeSearchQuery] = useState('');

  const [isDbPanelOpen, setIsDbPanelOpen] = useState(false);
  const [dbSearchQuery, setDbSearchQuery] = useState('');

  const [isConnectorPanelOpen, setIsConnectorPanelOpen] = useState(false);
  const [selectedConnectors, setSelectedConnectors] = useState<ConnectorInstance[]>([]);
  const [connectorSearchQuery, setConnectorSearchQuery] = useState('');
  const [isScheduleOpen, setScheduleOpen] = useState(false);
  const { connectors: connectorsList } = useConnectors();

  // HITL 确认轮询临时关闭：当前不需要写操作前的人工确认能力。
  // 恢复时把下一行改回 `loading && selectedConnectors.length > 0` 即可，
  // 后端 _PENDING_CONFIRMATIONS 通道 / ConfirmDialog 组件保持原样未删除。
  const isConfirmPollingActive = false;
  const { pendingConfirmation, approve, deny, dismiss } = useConfirmPolling({
    isActive: isConfirmPollingActive,
  });

  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);
  const [rightPanelView, setRightPanelView] = useState<PanelView>('execution');
  const [selectedCitationIndex, setSelectedCitationIndex] = useState<number | null>(null);
  const [pendingFinalization, setPendingFinalization] = useState<{
    responseId: string;
    summaryText: string;
    uploadedFilePath: string | null;
  } | null>(null);
  const [pendingSummaryPresentation, setPendingSummaryPresentation] = useState<{
    responseId: string;
    summaryText: string;
    targetView: 'html-preview' | 'image-preview' | 'skill-preview' | null;
  } | null>(null);
  const [summaryPresentationResponseId, setSummaryPresentationResponseId] = useState<string | null>(null);
  const summaryPresentationRef = useRef<SummaryPresentation | null>(null);
  const summaryPresentationResponseIdRef = useRef<string | null>(null);
  const summaryPresentationFullTextRef = useRef('');
  const [previewArtifact, setPreviewArtifact] = useState<Artifact | null>(null);

  const cancelSummaryPresentation = useCallback(() => {
    if (!summaryPresentationRef.current && !summaryPresentationResponseIdRef.current) return;

    summaryPresentationRef.current?.cancel();
    summaryPresentationRef.current = null;
    if (summaryPresentationFullTextRef.current) {
      setStreamingSummary(summaryPresentationFullTextRef.current);
    }
    summaryPresentationFullTextRef.current = '';
    summaryPresentationResponseIdRef.current = null;
    setSummaryPresentationResponseId(null);
    setPendingSummaryPresentation(null);
    setSummaryComplete(true);
  }, []);

  const handleUserPanelViewChange = useCallback(
    (view: PanelView) => {
      cancelSummaryPresentation();
      setRightPanelView(view);
    },
    [cancelSummaryPresentation],
  );

  // Active round tracking: which view message is currently selected for the right panel
  const [activeViewMsgId, setActiveViewMsgId] = useState<string | null>(null);
  // Devin-style: which sub-agent's process to show in the right panel (clicked
  // in the left SubAgentSection). null = show the main agent's execution.
  // Carries messageId so switching rounds cannot leak another round's sub-agent
  // of the same id into the view (sub_d1_0 from round A must not show round B's
  // sub_d1_0).
  const [activeSubAgent, setActiveSubAgent] = useState<{
    messageId: string;
    agentId: string;
  } | null>(null);

  // Track step IDs that belong to a terminate action so we can suppress them
  const terminatedStepIdsRef = useRef<Set<string>>(new Set());
  // Snapshot of the exact payload last sent to the agent, captured at send
  // time so "保存定时任务" can replay the real execution (file / database /
  // knowledge / skill / connectors) instead of a drifting UI state.
  const lastSentPayloadRef = useRef<ChatReplayPayload | null>(null);

  // AbortController of the in-flight chat request, stored so the stop button
  // and the conversation-switch effect can both reach it. Ownership stays
  // with the streaming loop in handleStart, which clears it in `finally`.
  const chatAbortControllerRef = useRef<AbortController | null>(null);

  const abortInFlightChat = useCallback(() => {
    chatAbortControllerRef.current?.abort();
  }, []);

  const handleStopGeneration = useCallback(() => {
    abortInFlightChat();
  }, [abortInFlightChat]);

  const [historyLoading, setHistoryLoading] = useState(false);
  const [contextStatus, setContextStatus] = useState<{
    state: 'OK' | 'WARNING' | 'ERROR';
    used_tokens: number;
    max_tokens: number;
    usage_percent: number;
    layer: string | null;
  } | null>(null);
  const [pendingQuestion, setPendingQuestion] = useState<{
    request_id: string;
    conv_id: string;
    questions: Array<{
      question: string;
      header: string;
      options: Array<{ label: string; description: string }>;
      multiple?: boolean;
      custom?: boolean;
    }>;
  } | null>(null);
  const [taskPlan, setTaskPlan] = useState<TaskItem[]>([]);

  const replyQuestion = useCallback(async (requestId: string, answers: string[][]) => {
    const res = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/chat/question/${requestId}/reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers }),
    });
    if (res.ok) {
      setPendingQuestion(null);
    }
  }, []);

  const rejectQuestion = useCallback(async (requestId: string) => {
    const res = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/chat/question/${requestId}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (res.ok) {
      setPendingQuestion(null);
    }
  }, []);

  // Fetch Data Sources
  const { data: dataSources, loading: _loadingSources } = useRequest(async () => {
    try {
      const response: any = await axios.get('/api/v2/serve/datasources');
      // ctx-axios interceptor returns response.data directly, so response is {success, data, ...}
      const result = response?.success !== undefined ? response : response?.data;
      if (result?.success) {
        return (result.data || []).map((item: any) => ({
          ...item,
          db_name: item.db_name || item.params?.name || item.params?.database || `${item.type}-${item.id}`,
          db_type: item.type,
        })) as DataSource[];
      }
      return [];
    } catch (e) {
      console.error('Failed to fetch datasources', e);
      return [];
    }
  });

  // Fetch Knowledge Bases
  const { data: knowledgeSpaces, loading: _loadingKnowledge } = useRequest(async () => {
    try {
      const response = await sendSpacePostRequest('/api/v1/knowledge/space/list', {});
      // ctx-axios interceptor returns response.data directly, so response is {success, data, ...}
      if (response?.success) {
        return response.data || [];
      }
      return [];
    } catch (e) {
      console.error('Failed to fetch knowledge spaces', e);
      return [];
    }
  });

  const normalizeText = (value: unknown): string => {
    if (typeof value === 'string') return value;
    if (value && typeof value === 'object') {
      const todoValue = (value as Record<string, unknown>).TODO;
      if (typeof todoValue === 'string') return todoValue;
      try {
        return JSON.stringify(value);
      } catch {
        return String(value);
      }
    }
    return value == null ? '' : String(value);
  };

  /** Extract the actual created skill name from shell_interpreter output.
   *  Uses priority-based matching to avoid returning 'skill-creator' (the tool path). */
  const extractCreatedSkillName = (allText: string): string | null => {
    // Priority 1: Skill 'xxx' initialized/packaged (quoted name from output)
    const quotedSkill = allText.match(/[Ss]kill\s+['"]([\w-]+)['"]/);
    if (quotedSkill) return quotedSkill[1];

    // Priority 2: Initializing/Packaging skill: xxx
    const colonSkill = allText.match(/(?:Initializing|Packaging)\s+skill:\s*(?:skills\/)?([\w-]+)/);
    if (colonSkill) return colonSkill[1];

    // Priority 3: Created skill directory: .../skills/xxx
    const createdDir = allText.match(/Created skill directory:.*\/skills\/([\w-]+)/);
    if (createdDir) return createdDir[1];

    // Priority 4: Last skills/xxx path, filtering out 'skill-creator'
    const allPaths = [...allText.matchAll(/skills\/([\w-]+)/g)].map(m => m[1]).filter(name => name !== 'skill-creator');
    if (allPaths.length > 0) return allPaths[allPaths.length - 1];

    return null;
  };

  // Fetch Skills/DBGPTs list
  const { data: skillsList, loading: _loadingSkills } = useRequest(async () => {
    try {
      const response = await axios.get(`${process.env.API_BASE_URL ?? ''}/api/v1/skills/list`);
      // ctx-axios interceptor returns response.data directly
      if (response?.success && Array.isArray(response.data)) {
        return response.data.map((item: any) => ({
          id: String(item.id || item.name),
          name: normalizeText(item.name),
          description: normalizeText(item.description),
          type: item.type === 'official' ? 'official' : 'personal',
          icon:
            item.skill_type === 'data_analysis'
              ? '📊'
              : item.skill_type === 'coding'
                ? '💻'
                : item.skill_type === 'web_search'
                  ? '🔍'
                  : item.skill_type === 'knowledge_qa'
                    ? '📚'
                    : item.skill_type === 'chat'
                      ? '💬'
                      : '⚡',
        })) as Skill[];
      }
      return [];
    } catch (e) {
      console.error('Failed to fetch skills', e);
      return [];
    }
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    cancelSummaryPresentation();
    const convId = router.query.id as string | undefined;
    if (convId && convId !== conversationId) {
      // Abort any in-flight turn before switching away — its stream would
      // otherwise keep writing into global UI state (loading, right panel)
      // of the newly opened conversation.
      abortInFlightChat();
      loadConversation(convId);
      // Rebuild the composer rail from the server-owned session files so a
      // conversation switch never leaks drafts from another session scope.
      void sessionFiles.rehydrateFromServer(convId);
      closeSessionFilePreview();
    } else if (!convId && conversationId) {
      // URL 中 id 消失（如点击 new_task / 探索广场），清空当前会话状态
      abortInFlightChat();
      setMessages([]);
      setConversationId(null);
      setQuery('');
      setExecutionMap({});
      setActiveMessageId(null);
      setActiveViewMsgId(null);
      setArtifacts([]);
      setRightPanelTab('preview');
      setStreamingSummary('');
      setSummaryComplete(false);
      setTaskPlan([]);
      sessionFiles.clearTurn();
      closeSessionFilePreview();
    }
  }, [abortInFlightChat, cancelSummaryPresentation, closeSessionFilePreview, router.query.id]);

  useEffect(() => {
    const lastView = [...messages].reverse().find(msg => msg.role === 'view');
    if (lastView?.id) {
      setActiveMessageId(lastView.id);
    }
  }, [messages]);

  interface Round {
    humanMsg: ChatMessage | null;
    viewMsg: ChatMessage | null;
  }

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
    if (activeViewMsgId) {
      const exists = rounds.some(r => r.viewMsg?.id === activeViewMsgId);
      if (exists) return activeViewMsgId;
    }
    const lastRound = rounds[rounds.length - 1];
    return lastRound?.viewMsg?.id || null;
  }, [activeViewMsgId, rounds]);

  const parseCsvLine = (line: string) => {
    const result: string[] = [];
    let current = '';
    let inQuotes = false;
    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      const nextChar = line[i + 1];
      if (char === '"') {
        if (inQuotes && nextChar === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === ',' && !inQuotes) {
        result.push(current);
        current = '';
      } else {
        current += char;
      }
    }
    result.push(current);
    return result.map(val => val.trim());
  };

  const _parseCsvText = (text: string, fileName?: string) => {
    const lines = text.split(/\r?\n/).filter(line => line.trim());
    if (!lines.length) return null;
    const header = parseCsvLine(lines[0]);
    const rows = lines.slice(1, 51).map((line, idx) => {
      const values = parseCsvLine(line);
      const row: Record<string, any> = { id: idx + 1 };
      header.forEach((col, i) => {
        row[col || `col_${i + 1}`] = values[i] ?? '';
      });
      return row;
    });
    return {
      kind: 'table' as const,
      file_name: fileName,
      columns: header.map(col => col || 'Column'),
      rows,
      shape: [lines.length - 1, header.length],
    };
  };

  const _getArtifactName = (outputType: string, content: any): string => {
    if (outputType === 'table') {
      const rowCount = content?.rows?.length || 0;
      const colCount = content?.columns?.length || 0;
      return `Data Table (${rowCount} rows × ${colCount} cols)`;
    }
    if (outputType === 'chart') {
      const chartType = content?.chartType || 'line';
      const chartTypeNames: Record<string, string> = {
        line: 'Line Chart',
        column: 'Column Chart',
        bar: 'Bar Chart',
        pie: 'Pie Chart',
        donut: 'Donut Chart',
        area: 'Area Chart',
        scatter: 'Scatter Plot',
        'dual-axes': 'Dual Axes Chart',
      };
      return content?.title || chartTypeNames[chartType] || 'Chart Visualization';
    }
    if (outputType === 'code') {
      return `Code Snippet`;
    }
    if (outputType === 'image') {
      return content?.name || 'Image';
    }
    if (outputType === 'markdown') {
      const preview = String(content).slice(0, 30);
      return `Document: ${preview}${String(content).length > 30 ? '...' : ''}`;
    }
    if (outputType === 'file') {
      return content?.name || content?.file_name || 'File';
    }
    return `${outputType} output`;
  };

  const extractCodeFileName = (code: string, stepLabel: string, index: number): string => {
    const saveMatch = code.match(/\.to_(?:excel|csv)\s*\(\s*['"]([^'"]+)['"]/);
    if (saveMatch) return saveMatch[1].split('/').pop() || saveMatch[1];
    const openMatch = code.match(/open\s*\(\s*['"]([^'"]+\.(?:py|txt|json|csv|xlsx?))['"]/);
    if (openMatch) return openMatch[1].split('/').pop() || openMatch[1];

    const savefigMatch = code.match(/savefig\s*\(\s*['"]([^'"]+)['"]/);
    if (savefigMatch) return savefigMatch[1].split('/').pop() || savefigMatch[1];

    const readMatch = code.match(/pd\.read_(?:csv|excel)\s*\(\s*['"]([^'"]+)['"]/);
    if (readMatch) {
      const srcName = (readMatch[1].split('/').pop() || readMatch[1]).replace(/\.[^.]+$/, '');
      return `analyze_${srcName}.py`;
    }

    const defMatch = code.match(/def\s+(\w+)\s*\(/);
    if (defMatch) return `${defMatch[1]}.py`;

    const classMatch = code.match(/class\s+(\w+)/);
    if (classMatch) return `${classMatch[1]}.py`;

    if (/import\s+matplotlib|plt\./.test(code)) return `visualization_${index + 1}.py`;
    if (/sns\.|import\s+seaborn/.test(code)) return `chart_${index + 1}.py`;
    if (/pd\.|import\s+pandas/.test(code)) return `data_processing_${index + 1}.py`;

    const label = stepLabel.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 30);
    return `${label}_${index}.py`;
  };

  const extractFileReferences = (
    text: string,
  ): Array<{ name: string; downloadable: boolean; size?: number; filePath?: string }> => {
    const refs: Array<{ name: string; downloadable: boolean; size?: number; filePath?: string }> = [];
    const filePattern = /[/\w\-.:]+\.(?:xlsx|xls|csv|py|json|txt|pdf|png|jpg|jpeg|html|md)/gi;
    const matches = text.match(filePattern) || [];
    const seen = new Set<string>();
    matches.forEach(m => {
      const name = m.split('/').pop() || m;
      const lower = name.toLowerCase();
      if (!seen.has(lower)) {
        seen.add(lower);
        // Preserve full path if it looks like an absolute path
        const filePath = m.startsWith('/') ? m : undefined;
        refs.push({ name, downloadable: true, filePath });
      }
    });
    return refs;
  };

  const downloadArtifact = async (artifact: Artifact) => {
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
          const filename = artifact.name || imgUrl.split('/').pop() || 'image.png';
          triggerBlobDownload(blob, filename);
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
        const blob = new Blob([htmlContent], { type: 'text/html' });
        triggerBlobDownload(blob, artifact.name || 'report.html');
        break;
      }
      case 'code': {
        const blob = new Blob([String(artifact.content)], { type: 'text/plain' });
        triggerBlobDownload(blob, artifact.name || 'code.py');
        break;
      }
      case 'table': {
        const rows = artifact.content?.rows || [];
        const columns = artifact.content?.columns?.map((c: any) => c.dataIndex || c.key || c) || [];
        const csvContent = [
          columns.join(','),
          ...rows.map((row: any) => columns.map((col: string) => JSON.stringify(row[col] ?? '')).join(',')),
        ].join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv' });
        triggerBlobDownload(blob, artifact.name?.replace(/\.\w+$/, '.csv') || 'table.csv');
        break;
      }
      case 'markdown':
      case 'summary': {
        const blob = new Blob([String(artifact.content)], { type: 'text/markdown' });
        triggerBlobDownload(blob, artifact.name || `${artifact.type}.md`);
        break;
      }
      case 'file': {
        const filePath = artifact.content?.file_path || artifact.content?.path || (artifact as any).filePath;
        if (filePath && filePath.includes('/images/')) {
          const imgName = filePath.split('/').pop();
          const resolvedUrl = `${process.env.API_BASE_URL || ''}/images/${imgName}`;
          try {
            const resp = await fetch(resolvedUrl);
            const blob = await resp.blob();
            triggerBlobDownload(blob, artifact.name || imgName || 'file');
          } catch {
            message.warning('文件暂不可下载');
          }
        } else if (filePath) {
          // Download via backend file download endpoint (for agent-created files)
          const downloadUrl = `${process.env.API_BASE_URL || ''}/api/v1/agent/files/download?file_path=${encodeURIComponent(filePath)}`;
          try {
            const resp = await fetch(downloadUrl);
            if (!resp.ok) {
              const errData = await resp.json().catch(() => ({}));
              message.warning(errData.detail || '文件暂不可下载');
              break;
            }
            const blob = await resp.blob();
            triggerBlobDownload(blob, artifact.name || filePath.split('/').pop() || 'file');
          } catch {
            message.warning('文件下载失败');
          }
        } else {
          message.warning('文件暂不可下载');
        }
        break;
      }
      default: {
        const blob = new Blob([JSON.stringify(artifact.content, null, 2)], { type: 'application/json' });
        triggerBlobDownload(blob, artifact.name || 'artifact.json');
      }
    }
  };

  const _copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(() => {
      message.success('Copied to clipboard');
    });
  };

  const _getArtifactIcon = (type: ArtifactType, chartType?: ChartType) => {
    switch (type) {
      case 'table':
        return <TableOutlined className='text-blue-500' />;
      case 'chart':
        if (chartType === 'pie' || chartType === 'donut') {
          return <PieChartOutlined className='text-green-500' />;
        }
        return <BarChartOutlined className='text-green-500' />;
      case 'code':
        return <CodeOutlined className='text-purple-500' />;
      case 'image':
        return <FileImageOutlined className='text-pink-500' />;
      case 'markdown':
        return <FileTextOutlined className='text-orange-500' />;
      case 'summary':
        return <FileTextOutlined className='text-emerald-500' />;
      case 'file':
        return <FileOutlined className='text-gray-500' />;
      default:
        return <FileOutlined className='text-gray-500' />;
    }
  };

  // Build artifacts from execution data — shared between live streaming and history restore
  const buildArtifactsFromExecution = useCallback(
    (
      messageId: string,
      execution: {
        steps: ExecutionStep[];
        outputs: Record<string, ExecutionOutput[]>;
        subAgents?: Record<string, SubAgentState>;
      },
      summaryText?: string,
      filePath?: string | null,
    ): Artifact[] => {
      const finalArtifacts: Artifact[] = [];
      const now = Date.now();
      const seenCodeHashes = new Set<string>();

      if (execution) {
        const allSteps = execution.steps || [];
        allSteps.forEach(step => {
          const stepOutputs = execution.outputs[step.id] || [];
          stepOutputs.forEach((output, oIdx) => {
            if (output.output_type === 'code') {
              const codeStr = String(output.content || '').trim();
              const hash = codeStr.slice(0, 200);
              if (codeStr && !seenCodeHashes.has(hash)) {
                seenCodeHashes.add(hash);
                const fileName = extractCodeFileName(codeStr, step.action || step.id, oIdx);
                finalArtifacts.push({
                  id: `${messageId}-code-${step.id}-${oIdx}`,
                  type: 'code',
                  name: fileName,
                  content: codeStr,
                  createdAt: now,
                  messageId,
                  stepId: step.id,
                  downloadable: true,
                });
              }
            } else if (output.output_type === 'file') {
              finalArtifacts.push({
                id: `${messageId}-file-${step.id}-${oIdx}`,
                type: 'file',
                name: output.content?.name || output.content?.file_name || 'File',
                content: output.content,
                createdAt: now,
                messageId,
                stepId: step.id,
                downloadable: true,
                size: output.content?.size,
              });
            } else if (output.output_type === 'html') {
              const htmlContent =
                typeof output.content === 'string'
                  ? output.content
                  : output.content?.content || output.content?.html || String(output.content);
              const htmlTitle = output.content?.title || 'Report';
              finalArtifacts.push({
                id: `${messageId}-html-${step.id}-${oIdx}`,
                type: 'html',
                name: `${htmlTitle}.html`,
                content: htmlContent,
                createdAt: now,
                messageId,
                stepId: step.id,
                downloadable: true,
              });
            } else if (output.output_type === 'image') {
              const imgUrl =
                typeof output.content === 'string'
                  ? output.content
                  : output.content?.url || output.content?.src || String(output.content);
              const imgName = imgUrl.split('/').pop() || `image_${oIdx}.png`;
              const displayName = imgName.replace(/^[a-f0-9]{8}_/, '');
              finalArtifacts.push({
                id: `${messageId}-img-${step.id}-${oIdx}`,
                type: 'image',
                name: displayName,
                content: imgUrl,
                createdAt: now,
                messageId,
                stepId: step.id,
                downloadable: true,
              });
            }
          });

          // For shell_interpreter steps, extract file paths from code/text outputs
          // and create downloadable file artifacts
          if (step.action === 'shell_interpreter') {
            // Match both absolute paths and relative filenames with extensions
            const absPathPattern = /(?:\/[\w\-.]+)+\.\w{1,10}/g;
            const relFilePattern = /(?:>|>>|\btee\b|\btouch\b)\s+([\w\-./ ]+\.\w{1,10})/g;
            const seenFilePaths = new Set<string>();
            stepOutputs.forEach(output => {
              if (output.output_type === 'code' || output.output_type === 'text') {
                const text = String(output.content || '');
                // Look for file creation patterns
                const hasFileCreation = /(?:>|>>|\btee\b|\bcat\b.*>|\bcp\b|\bmv\b|\btouch\b|\becho\b.*>)/.test(text);
                if (hasFileCreation) {
                  const foundPaths: string[] = [];
                  // Extract absolute paths
                  const absMatches = text.match(absPathPattern) || [];
                  foundPaths.push(...absMatches);
                  // Extract relative paths after redirection operators
                  let relMatch;
                  while ((relMatch = relFilePattern.exec(text)) !== null) {
                    const p = relMatch[1].trim();
                    if (p && !p.startsWith('/')) foundPaths.push(p);
                  }
                  foundPaths.forEach(fp => {
                    // Normalize: strip leading ./ if present
                    const normalized = fp.replace(/^\.\//, '');
                    const fileName = normalized.split('/').pop() || normalized;
                    if (!seenFilePaths.has(fileName.toLowerCase())) {
                      seenFilePaths.add(fileName.toLowerCase());
                      const alreadyHasFile = finalArtifacts.some(
                        a =>
                          (a.type === 'file' || a.type === 'image') && a.name.toLowerCase() === fileName.toLowerCase(),
                      );
                      if (!alreadyHasFile) {
                        // Use the path as-is; backend resolves relative paths against pilot/tmp
                        finalArtifacts.push({
                          id: `${messageId}-shellfile-${step.id}-${fileName}`,
                          type: 'file',
                          name: fileName,
                          content: { name: fileName, file_path: normalized },
                          createdAt: now,
                          messageId,
                          stepId: step.id,
                          downloadable: true,
                          filePath: normalized,
                        });
                      }
                    }
                  });
                }
              }
            });
          }
        });
      }

      // Sub-agent artifacts: when restoring from history, the live
      // ``subagent.artifacts`` SSE event is not replayed, so scan each
      // sub-agent's step ``chunks`` for image/html (same shape the backend
      // forwards in agent.step) and materialize them as Artifacts tagged with
      // their source agent. Mirrors the live path in processEvent.
      const subAgents = (execution as { subAgents?: Record<string, SubAgentState> }).subAgents;
      if (subAgents) {
        for (const agent of Object.values(subAgents)) {
          const persistedArtifactUrls = new Set((agent.artifacts || []).map(artifact => artifact.url));
          (agent.artifacts || []).forEach((artifact, artifactIndex) => {
            const artifactType = artifact.type === 'image' ? 'image' : artifact.type === 'html' ? 'html' : 'file';
            const fallbackName = artifact.url.split('/').pop() || `subagent-artifact-${artifactIndex}`;
            const name = artifact.title || fallbackName;
            finalArtifacts.push({
              id: `${messageId}-subagent-ref-${agent.agentId}-${artifactIndex}`,
              type: artifactType,
              name: artifactType === 'html' && !name.endsWith('.html') ? `${name}.html` : name,
              content: artifactType === 'file' ? { name, file_path: artifact.url } : artifact.url,
              createdAt: now,
              messageId,
              stepId: agent.agentId,
              sourceAgent: agent.name,
              downloadable: true,
              ...(artifactType === 'file' ? { filePath: artifact.url } : {}),
            });
          });
          (agent.steps || []).forEach((step, sIdx) => {
            (step.chunks || []).forEach((chunk, cIdx) => {
              const ot = chunk.output_type;
              const content = chunk.content;
              if (ot === 'image' && typeof content === 'string') {
                if (persistedArtifactUrls.has(content)) return;
                const imgName = content.split('/').pop() || `image_${sIdx}_${cIdx}.png`;
                finalArtifacts.push({
                  id: `${messageId}-subagent-${agent.agentId}-${sIdx}-${cIdx}`,
                  type: 'image',
                  name: imgName.replace(/^[a-f0-9]{8}_/, ''),
                  content,
                  createdAt: now,
                  messageId,
                  stepId: agent.agentId,
                  sourceAgent: agent.name,
                  downloadable: true,
                });
              } else if (ot === 'html' && typeof content === 'string') {
                if (persistedArtifactUrls.has(content)) return;
                const htmlTitle = (chunk as { title?: string }).title || agent.name;
                finalArtifacts.push({
                  id: `${messageId}-subagent-${agent.agentId}-${sIdx}-${cIdx}`,
                  type: 'html',
                  name: `${htmlTitle}.html`,
                  content,
                  createdAt: now,
                  messageId,
                  stepId: agent.agentId,
                  sourceAgent: agent.name,
                  downloadable: true,
                });
              }
            });
          });
        }
      }

      if (summaryText) {
        const fileRefs = extractFileReferences(summaryText);
        fileRefs.forEach((ref, idx) => {
          const alreadyExists = finalArtifacts.some(a => a.name.toLowerCase() === ref.name.toLowerCase());
          if (!alreadyExists) {
            finalArtifacts.push({
              id: `${messageId}-fileref-${idx}`,
              type: 'file',
              name: ref.name,
              content: { name: ref.name, file_path: ref.filePath },
              createdAt: now,
              messageId,
              downloadable: ref.downloadable,
              filePath: ref.filePath,
              size: ref.size,
            });
          }
        });
      }

      if (filePath) {
        const uploadName = filePath.split('/').pop() || 'uploaded_file';
        const alreadyExists = finalArtifacts.some(a => a.name.toLowerCase() === uploadName.toLowerCase());
        if (!alreadyExists) {
          finalArtifacts.push({
            id: `${messageId}-upload`,
            type: 'file',
            name: uploadName,
            content: { name: uploadName, file_path: filePath },
            createdAt: now,
            messageId,
            downloadable: true,
          });
        }
      }

      // Deduplicate: for artifacts with the same name+type, keep only the last one
      const deduped: Artifact[] = [];
      const seen = new Map<string, number>();
      for (let i = finalArtifacts.length - 1; i >= 0; i--) {
        const key = `${finalArtifacts[i].type}:${finalArtifacts[i].name}`;
        if (!seen.has(key)) {
          seen.set(key, i);
          deduped.unshift(finalArtifacts[i]);
        }
      }

      return deduped;
    },
    [],
  );

  useEffect(() => {
    if (!pendingFinalization) return;

    const { responseId, summaryText, uploadedFilePath: finalFilePath } = pendingFinalization;
    const execution = executionMap[responseId];
    const deduped = buildArtifactsFromExecution(
      responseId,
      execution || { steps: [], outputs: {} },
      summaryText,
      finalFilePath,
    );

    setArtifacts(prevArtifacts => {
      const filtered = prevArtifacts.filter(artifact => artifact.messageId !== responseId);
      return [...filtered, ...deduped];
    });

    const htmlArtifact = deduped.find(artifact => artifact.type === 'html');
    const imageArtifact = deduped.find(artifact => artifact.type === 'image');
    let targetView: 'html-preview' | 'image-preview' | 'skill-preview' | null = null;
    if (htmlArtifact) {
      setPreviewArtifact(htmlArtifact as Artifact);
      targetView = 'html-preview';
    } else if (imageArtifact) {
      setPreviewArtifact(imageArtifact as Artifact);
      targetView = 'image-preview';
    }

    if (execution) {
      const skillStep = execution.steps.find(step => {
        if (step.action !== 'shell_interpreter') return false;
        const detailHas = step.detail?.includes('package_skill') || step.detail?.includes('init_skill');
        const inputHas = step.actionInput?.includes('package_skill') || step.actionInput?.includes('init_skill');
        const outputTexts = (execution.outputs[step.id] || []).map(output => String(output.content)).join(' ');
        const outputHas =
          outputTexts.includes('package_skill') ||
          outputTexts.includes('init_skill') ||
          outputTexts.includes('Successfully packaged');
        return detailHas || inputHas || outputHas;
      });
      if (skillStep) {
        const allText = [
          skillStep.actionInput || '',
          skillStep.detail || '',
          ...(execution.outputs[skillStep.id] || []).map(output => String(output.content)),
        ].join(' ');
        const skillName = extractCreatedSkillName(allText);
        if (skillName) {
          setCreatedSkillNames(prev => ({ ...prev, [responseId]: skillName }));
          targetView = 'skill-preview';
        }
      }
    }

    if (targetView) {
      setRightPanelCollapsed(false);
    }

    // Artifact preparation and visible navigation are intentionally separate.
    // Keep the clean summary visible first; the bounded presentation controller
    // will open the prepared preview after the reveal/hold phase completes.
    if (summaryText && summaryPresentationResponseIdRef.current === responseId) {
      setPendingSummaryPresentation({ responseId, summaryText, targetView });
    } else if (!summaryText && targetView) {
      setRightPanelView(targetView);
    }

    setPendingFinalization(null);
  }, [buildArtifactsFromExecution, executionMap, pendingFinalization]);

  useEffect(() => {
    if (!pendingSummaryPresentation) return;

    const { responseId, summaryText, targetView } = pendingSummaryPresentation;
    if (
      summaryPresentationResponseIdRef.current !== responseId ||
      activeViewMsgId !== responseId ||
      rightPanelView !== 'summary'
    ) {
      cancelSummaryPresentation();
      return;
    }

    const presentation = createSummaryPresentation({
      summary: summaryText,
      reducedMotion:
        typeof window !== 'undefined' &&
        typeof window.matchMedia === 'function' &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches,
      onSummaryUpdate: (content, complete) => {
        if (summaryPresentationResponseIdRef.current !== responseId) return;
        setStreamingSummary(content);
        setSummaryComplete(complete);
      },
      onPreviewReady: () => {
        if (summaryPresentationResponseIdRef.current !== responseId) return;

        summaryPresentationRef.current = null;
        summaryPresentationFullTextRef.current = '';
        summaryPresentationResponseIdRef.current = null;
        setStreamingSummary(summaryText);
        setSummaryComplete(true);
        setSummaryPresentationResponseId(null);
        setPendingSummaryPresentation(null);
        if (targetView) {
          setRightPanelView(targetView);
          setRightPanelCollapsed(false);
        }
      },
    });

    summaryPresentationRef.current = presentation;
    presentation.start();

    return () => {
      presentation.cancel();
      if (summaryPresentationRef.current === presentation) {
        summaryPresentationRef.current = null;
      }
    };
  }, [activeViewMsgId, cancelSummaryPresentation, pendingSummaryPresentation, rightPanelView]);

  const performStart = async (
    inputQuery = query,
    overrideSkill?: Skill | null,
    overrideDb?: DataSource | null,
    explicitLegacyFile?: LegacyServerFile | null,
  ) => {
    const effectiveSkill = overrideSkill !== undefined ? overrideSkill : selectedSkill;
    const effectiveDb = overrideDb !== undefined ? overrideDb : selectedDb;
    if (
      (!inputQuery.trim() && !hasSessionFileDrafts && !hasLegacyFile && !explicitLegacyFile) ||
      loading ||
      queuedSendAfterUpload
    )
      return;

    cancelSummaryPresentation();

    let finalQuery = inputQuery;
    const appCode = 'chat_react_agent';
    const chatMode = 'chat_react_agent';

    // The conversation id must be settled before preparing file sends so the
    // uploads (bound at pick time) and this request share one session scope.
    const currentConvId = conversationIdRef.current || generateUUID();
    if (!conversationIdRef.current) {
      conversationIdRef.current = currentConvId;
      setConversationId(currentConvId);
    }
    let sendSnapshot: SessionFilesSendSnapshot | null = null;

    // A preloaded example is staged and snapshotted atomically from this
    // explicit value, so the first auto-send never waits for React to commit
    // the attachment-rail state. Manual uploads keep the existing queued
    // file_ids flow below; the session-files module rejects protocol mixing.
    if (explicitLegacyFile) {
      const staged = sessionFiles.stageLegacyForSend(explicitLegacyFile, currentConvId);
      if (!staged.ok) {
        message.error('加载示例失败: ' + staged.error);
        return;
      }
      sendSnapshot = staged.snapshot;
    } else if (hasSessionFileDrafts || hasLegacyFile) {
      if (sessionFiles.files.some(draft => draft.validation.status !== 'ok')) {
        message.error('存在未通过校验的附件，请先移除后再发送');
        return;
      }
      if (sessionFiles.hasHardFailures) {
        message.error('有附件上传失败，请重试或移除后再发送');
        return;
      }
      try {
        setQueuedSendAfterUpload(sessionFiles.isUploading);
        sendSnapshot = await sessionFiles.prepare(currentConvId);
      } catch (prepareErr: any) {
        message.error(prepareErr?.message || '附件校验失败，请重试');
        return;
      } finally {
        setQueuedSendAfterUpload(false);
      }
      if (sendSnapshot && sendSnapshot.fileIds.length === 0 && !sendSnapshot.legacyFile) {
        sendSnapshot = null;
      }
    }
    if (sendSnapshot?.legacyFile && !finalQuery.trim()) {
      // Legacy example-card default (unchanged from the preloaded flow).
      finalQuery = 'Analyze the uploaded file.';
    }
    // Construct context prefix for non-legacy queries. Legacy example sends
    // reproduce the old payload, which never carried a context prefix.
    if (!sendSnapshot?.legacyFile) {
      const contextParts = [];
      if (effectiveDb) contextParts.push(`[Database: ${effectiveDb.db_name}]`);
      if (selectedKnowledge) contextParts.push(`[Knowledge: ${selectedKnowledge.name}]`);
      if (contextParts.length > 0) {
        finalQuery = `${contextParts.join(' ')} ${inputQuery}`;
      }
    }

    // Conversation id was already settled above (see send gating).
    // const snapshot so TS narrowing survives inside the map closure below.
    const filesAttachedThisSend: SessionFilesSendSnapshot | null = sendSnapshot;

    // Calculate current order
    const currentOrder = Math.floor(messages.length / 2) + 1;

    const responseId = generateUUID();

    const humanId = generateUUID();

    // Add user message and AI placeholder message
    setMessages(prev => [
      ...prev,
      {
        id: humanId,
        role: 'human',
        context: inputQuery,
        order: currentOrder,
        attachedFiles: filesAttachedThisSend ? snapshotsForSend(filesAttachedThisSend) : undefined,
        attachedKnowledge: selectedKnowledge ?? undefined,
        attachedSkill: effectiveSkill ? { name: effectiveSkill.name, id: effectiveSkill.id } : undefined,
        attachedDb: effectiveDb ? { db_name: effectiveDb.db_name, db_type: effectiveDb.db_type } : undefined,
        attachedConnectors:
          selectedConnectors.length > 0
            ? selectedConnectors.map(c => ({
                id: c.id,
                connector_type: c.connector_type,
                display_name: c.display_name,
              }))
            : undefined,
      },
      {
        id: responseId,
        role: 'view',
        context: '',
        order: currentOrder,
        thinking: true,
      },
    ]);

    setLoading(true);
    setQuery(''); // Clear input
    setStreamingSummary('');
    setSummaryComplete(false);
    setSelectedCitationIndex(null);
    setPendingFinalization(null);
    setPendingSummaryPresentation(null);
    setActiveViewMsgId(responseId); // Auto-switch right panel to new round

    const controller = new AbortController();
    chatAbortControllerRef.current = controller;
    terminatedStepIdsRef.current.clear();
    setExecutionMap(prev => ({
      ...prev,
      [responseId]: {
        steps: [],
        outputs: {},
        activeStepId: null,
        collapsed: false,
        stepThoughts: {},
      },
    }));
    setActiveMessageId(responseId);

    // Build ext_info once and reuse it for both the live request and the
    // snapshot captured for "保存定时任务", so a saved task replays the exact
    // same context (files / database / knowledge / skill / connectors).
    const baseExtInfo: Record<string, any> = {
      ...(effectiveSkill ? { skill_id: effectiveSkill.id, skill_name: effectiveSkill.name } : {}),
      ...(effectiveDb ? { database_name: effectiveDb.db_name, database_type: effectiveDb.db_type } : {}),
      ...(selectedKnowledge
        ? { knowledge_space_name: selectedKnowledge.name, knowledge_space_id: selectedKnowledge.id }
        : {}),
      ...(selectedConnectors.length > 0 ? { connector_ids: selectedConnectors.map(c => c.id) } : {}),
    };
    // Session-file sends travel via file_ids (+ display-safe task snapshot);
    // zero files keep the legacy payload byte-for-byte unchanged.
    const extInfo = extInfoForSend(baseExtInfo, filesAttachedThisSend);
    const selectParam = appCode === 'chat_react_agent' ? '' : appCode;

    // Snapshot the exact payload being sent (minus the per-run conv_uid, which
    // each scheduled run regenerates) so buildSnapshot replays this real run.
    // version 2 marks the session-file file_ids contract; legacy file_path
    // example sends stay on version 1 so task replay reuses the same protocol.
    lastSentPayloadRef.current = {
      version: filesAttachedThisSend && filesAttachedThisSend.fileIds.length > 0 ? 2 : 1,
      user_input: finalQuery,
      chat_mode: chatMode,
      model_name: model,
      select_param: selectParam,
      temperature: 0.6,
      max_new_tokens: 4000,
      ext_info: extInfo,
    };

    try {
      const response = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/chat/react-agent`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conv_uid: currentConvId,
          chat_mode: chatMode,
          model_name: model,
          user_input: finalQuery,
          temperature: 0.6,
          max_new_tokens: 4000,
          select_param: selectParam,
          ext_info: extInfo,
        }),
        signal: controller.signal,
      });

      if (!response.body) {
        throw new Error('No response body');
      }

      // Submission accepted by the server. The composer rail intentionally
      // keeps the sent files: they stay attached to the conversation scope
      // (file_ids are server-side already, so follow-up questions reuse them
      // without re-uploading) until the user removes them manually, switches
      // conversation, or clears the chat — same semantics as the legacy
      // single-file protocol.

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
        } catch (_err) {
          return;
        }
        if (payload.type === 'context.status') {
          const budget = Number(payload.budget ?? 0);
          if (!Number.isFinite(budget) || budget <= 0) {
            setContextStatus(null);
            return;
          }
          const stateMap: Record<string, 'OK' | 'WARNING' | 'ERROR'> = {
            normal: 'OK',
            warning: 'WARNING',
            error: 'ERROR',
            critical: 'ERROR',
            overflow: 'ERROR',
          };
          setContextStatus({
            state: stateMap[payload.state] || 'OK',
            used_tokens: payload.used ?? 0,
            max_tokens: budget,
            usage_percent: (payload.ratio ?? 0) * 100,
            layer: payload.compact_layer ?? null,
          });
          return;
        }
        if (
          payload.type === 'agent.start' ||
          payload.type === 'agent.step' ||
          payload.type === 'agent.done' ||
          payload.type === 'subagent.artifacts'
        ) {
          // Parallel sub-agent events -> grouped card state. Parsing is a
          // pure function in use-subagent-stream; the apply (setState) stays
          // here because processEvent closes over setExecutionMap (review I3).
          const partial = parseSubAgentEvent(payload);
          if (!partial) return;
          // Artifacts flow into the GLOBAL artifacts list (files tab / preview /
          // download) — a separate state from executionMap, so it gets its own
          // setter. Dedup by id so a replayed event cannot stack duplicates.
          if (partial.artifactItems && partial.artifactItems.length > 0) {
            const newArts = buildSubAgentArtifacts(partial.artifactItems, responseId);
            setArtifacts(prev => {
              const ids = new Set(prev.map(a => a.id));
              const merged = [...prev];
              for (const a of newArts) {
                if (!ids.has(a.id)) merged.push(a);
              }
              return merged;
            });
          }
          setExecutionMap(prev => {
            const current = prev[responseId] || {
              steps: [],
              outputs: {},
              activeStepId: null,
              collapsed: false,
              stepThoughts: {},
            };
            const subAgents: Record<string, SubAgentState> = { ...(current.subAgents || {}) };
            if (partial.upsert) {
              const existing = subAgents[partial.upsert.agentId];
              // agent.done carries status + final summary/timing. Merge those
              // onto the existing row while preserving start/step metadata.
              subAgents[partial.upsert.agentId] = existing
                ? {
                    ...existing,
                    status: partial.upsert.status,
                    result: partial.upsert.result ?? existing.result,
                    elapsedMs: partial.upsert.elapsedMs ?? existing.elapsedMs,
                  }
                : partial.upsert;
            }
            if (partial.stepUpdate) {
              const { agentId, step } = partial.stepUpdate;
              const existing = subAgents[agentId];
              if (existing) {
                subAgents[agentId] = {
                  ...existing,
                  steps: [...existing.steps, step],
                  currentAction: step.label,
                };
              }
            }
            // Per-agent artifact count: each item already carries its source
            // agent_id, so accumulate per row for the aggregate-card badge.
            if (partial.artifactItems && partial.artifactItems.length > 0) {
              const countByAgent: Record<string, number> = {};
              for (const it of partial.artifactItems) {
                countByAgent[it.agent_id] = (countByAgent[it.agent_id] || 0) + 1;
              }
              for (const [aid, n] of Object.entries(countByAgent)) {
                const existing = subAgents[aid];
                if (existing) {
                  subAgents[aid] = {
                    ...existing,
                    artifactCount: (existing.artifactCount || 0) + n,
                  };
                }
              }
            }
            // Aggregate header count = sum of per-row counts (always
            // consistent, immune to event replay / ordering quirks).
            const subAgentArtifacts = Object.values(subAgents).reduce((sum, a) => sum + (a.artifactCount || 0), 0);
            return { ...prev, [responseId]: { ...current, subAgents, subAgentArtifacts } };
          });
          return;
        }
        if (payload.type === 'question.asked') {
          setPendingQuestion(payload);
          return;
        }
        if (payload.type === 'question.replied' || payload.type === 'question.rejected') {
          setPendingQuestion(null);
          return;
        }
        if (payload.type === 'plan.update') {
          if (Array.isArray(payload.tasks)) {
            const nextTasks = payload.tasks as TaskItem[];
            setTaskPlan(nextTasks);
            setMessages(prev =>
              prev.map(msg => {
                if (msg.id !== responseId || msg.role !== 'view') return msg;
                return { ...msg, taskPlan: nextTasks };
              }),
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
            const existingThoughts = current.stepThoughts || {};
            const nextThoughts = existingThoughts;
            // Check if step already exists - if so, update it (especially phase) instead of creating duplicate
            const existingStepIndex = current.steps.findIndex(s => s.id === id);
            let nextSteps;
            if (existingStepIndex >= 0) {
              // Update existing step with new title/phase
              nextSteps = current.steps.map((step, idx) =>
                idx === existingStepIndex
                  ? {
                      ...step,
                      title: payload.title,
                      detail: payload.detail,
                      phase: payload.phase,
                      todoMeta: payload.todo_meta || step.todoMeta,
                      status: 'running' as const,
                    }
                  : step.status === 'running'
                    ? { ...step, status: 'done' }
                    : step,
              );
            } else {
              // New step - mark running steps as done and add new step
              nextSteps = [
                ...current.steps.map(item => (item.status === 'running' ? { ...item, status: 'done' } : item)),
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
                stepThoughts: nextThoughts,
                // Only auto-focus for existing step updates (e.g., "思考中" -> "sql_query").
                // New placeholder steps wait for step.meta to get real content before stealing focus.
                activeStepId: existingStepIndex >= 0 ? id : current.activeStepId || id,
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
              const nextSteps = current.steps.filter(item => item.id !== payload.id);
              const nextActiveStepId = current.activeStepId === payload.id ? null : current.activeStepId;
              return {
                ...prev,
                [responseId]: { ...current, steps: nextSteps, activeStepId: nextActiveStepId },
              };
            });
            return;
          }
          // Clear manual step selection so the right panel auto-tracks this step
          if (payload.action) {
            setSelectedStepId(null);
          }
          setExecutionMap(prev => {
            const current = prev[responseId];
            if (!current) return prev;
            // Build detail from action only (thought goes to stepThoughts)
            const nextSteps = current.steps.map(item => {
              if (item.id !== payload.id) return item;
              const parts = [] as string[];
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
            // Route model-provided action display fields to the subtle status row.
            const displayThought = buildActionDisplayText({
              actionIntention: payload.action_intention,
              actionReason: payload.action_reason,
              thought: payload.thought,
            });
            const nextThoughts = displayThought
              ? {
                  ...current.stepThoughts,
                  [payload.id]: displayThought,
                }
              : current.stepThoughts;
            return {
              ...prev,
              [responseId]: {
                ...current,
                steps: nextSteps,
                stepThoughts: nextThoughts,
                // Focus right panel on this step when it receives action content
                ...(payload.action ? { activeStepId: payload.id } : {}),
              },
            };
          });
        } else if (payload.type === 'step.output') {
          if (terminatedStepIdsRef.current.has(payload.id || '')) return;
          setExecutionMap(prev => {
            const current = prev[responseId];
            if (!current) return prev;
            const targetId = current.activeStepId;
            if (!targetId) return prev;
            const nextSteps = current.steps.map(item => {
              if (item.id !== targetId) return item;
              const detail = `${item.detail}\n${payload.detail}`.trim();
              return { ...item, detail };
            });
            return { ...prev, [responseId]: { ...current, steps: nextSteps } };
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
            return {
              ...prev,
              [responseId]: {
                ...current,
                outputs: { ...current.outputs, [targetId]: list },
              },
            };
          });

          // Artifacts are now generated at task completion (final event),
          // not during streaming — to avoid showing intermediate outputs as artifacts
        } else if (payload.type === 'step.done') {
          const id = payload.id;
          if (terminatedStepIdsRef.current.has(id || '')) return;
          setExecutionMap(prev => {
            const current = prev[responseId];
            if (!current) return prev;
            const targetId = id || current.activeStepId;
            if (!targetId) return prev;
            const nextSteps = current.steps.map(item =>
              item.id === targetId ? { ...item, status: payload.status || 'done' } : item,
            );
            return { ...prev, [responseId]: { ...current, steps: nextSteps } };
          });
        } else if (payload.type === 'step.thought') {
          // Raw model reasoning is intentionally not rendered in the user-facing
          // timeline. Display copy must come from step.meta action_intention or
          // action_reason, which are constrained to concise, readable text.
          return;
        } else if (payload.type === 'final') {
          const finalAnswer = decodeFinalEvent(payload);
          const summaryText = cleanFinalContent(finalAnswer.content);
          cancelSummaryPresentation();
          setExecutionMap(prev => {
            const current = prev[responseId];
            if (!current) return prev;
            const nextSteps = current.steps.map(item =>
              item.status === 'running' ? { ...item, status: 'done' as const } : item,
            );
            return { ...prev, [responseId]: { ...current, steps: nextSteps } };
          });
          setMessages(prev =>
            prev.map(msg => {
              if (msg.id !== responseId || msg.role !== 'view') return msg;
              return {
                ...msg,
                context: summaryText,
                citations: finalAnswer.citations,
                thinking: false,
              };
            }),
          );
          setTaskPlan([]);
          setActiveMessageId(responseId);
          setSelectedCitationIndex(finalAnswer.citations[0]?.index ?? null);

          if (summaryText) {
            const firstSummaryCharacter = summaryText.match(/^./u)?.[0] || summaryText;
            summaryPresentationResponseIdRef.current = responseId;
            summaryPresentationFullTextRef.current = summaryText;
            setSummaryPresentationResponseId(responseId);
            setStreamingSummary(firstSummaryCharacter);
            setSummaryComplete(false);
            setRightPanelTab('summary');
            setRightPanelView('summary');
            setRightPanelCollapsed(false);
          } else if (finalAnswer.citations.length > 0) {
            setStreamingSummary('');
            setSummaryComplete(true);
            setRightPanelView('references');
          } else {
            setStreamingSummary('');
            setSummaryComplete(true);
          }

          // Final is already a complete server event. Build artifacts now;
          // the bounded summary presentation controls only visible navigation.
          // uploadedFilePath only exists for the legacy single-file protocol;
          // session-file (file_ids) sends carry no server path client-side.
          setPendingFinalization({
            responseId,
            summaryText,
            uploadedFilePath: filesAttachedThisSend?.legacyFile?.file_path ?? null,
          });
        } else if (payload.type === 'done') {
          setLoading(false);
        }
      };

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        parts.forEach(processEvent);
      }
    } catch (err: any) {
      if (err?.name === 'AbortError' || controller.signal.aborted) {
        // User-initiated stop (stop button, or the conversation-switch effect
        // aborting the in-flight request). Not an error: keep the partial
        // round in place and mark it stopped. Updates are keyed by responseId
        // and guarded by conversation ownership, so an abort triggered by
        // switching away is a safe no-op on the newly shown conversation.
        if (conversationIdRef.current === currentConvId) {
          setExecutionMap(prev => {
            const current = prev[responseId];
            if (!current) return prev;
            const nextSteps = current.steps.map(item =>
              item.status === 'running' ? { ...item, status: 'failed' as const } : item,
            );
            return { ...prev, [responseId]: { ...current, steps: nextSteps } };
          });
          setMessages(prev =>
            prev.map(msg => {
              if (msg.id !== responseId || msg.role !== 'view') return msg;
              const partial = msg.context?.trim();
              const stoppedMark = t('generation_stopped');
              return {
                ...msg,
                context: partial ? `${partial}\n\n_${stoppedMark}_` : `_${stoppedMark}_`,
                thinking: false,
              };
            }),
          );
          setTaskPlan([]);
        }
      } else {
        message.error(err?.message || 'Failed to get response');
        setMessages(prev => {
          const newMessages = [...prev];
          const lastMsg = newMessages[newMessages.length - 1];
          if (lastMsg && lastMsg.role === 'view') {
            lastMsg.context = err?.message || 'Error occurred';
            lastMsg.thinking = false;
          }
          return newMessages;
        });
      }
    } finally {
      if (chatAbortControllerRef.current === controller) {
        chatAbortControllerRef.current = null;
      }
      setLoading(false);
    }
  };

  const handleStart = async (...args: Parameters<typeof performStart>): Promise<void> => {
    // React state is only a UI projection and may be stale in callbacks that
    // crossed an await. These refs serialize every send entry point, including
    // the composer and delayed example-card execution.
    if (sendInFlightRef.current || exampleRunInFlightRef.current) return;
    sendInFlightRef.current = true;
    try {
      await performStart(...args);
    } finally {
      sendInFlightRef.current = false;
    }
  };

  const handleExampleClick = async (example: (typeof EXAMPLE_CARDS)[number]) => {
    const queryKey = `example_${example.id}_query`;
    const queryVal = t(queryKey) as string;
    const translatedQuery = (queryVal && queryVal !== queryKey ? queryVal : example.query) as string;

    if (loading || sendInFlightRef.current || exampleRunInFlightRef.current) return;
    exampleRunInFlightRef.current = true;

    try {
      message.loading({ content: '正在加载示例...', key: 'example-loading', duration: 0 });
      let exampleLegacyFile: LegacyServerFile | null = null;

      // Example files already exist on the server: materialize the selected
      // file, then explicitly hand it to this turn. handleStart atomically
      // stages the read-only rail item and freezes the legacy file_path send.
      if (example.fileName) {
        if (hasSessionFileDrafts) {
          message.destroy('example-loading');
          message.warning('示例文件与本地上传的附件不能混用，请先移除已选附件');
          return;
        }
        const res = await axios.post(`${process.env.API_BASE_URL ?? ''}/api/v1/examples/use`, {
          example_id: example.id,
        });

        if (res?.success && res?.data) {
          exampleLegacyFile = {
            name: example.fileName,
            size: example.fileSize || 0,
            media_type: example.fileType,
            file_path: res.data,
          };
        } else {
          message.destroy('example-loading');
          const errMsg = res?.err_msg || 'Unknown error';
          message.error('加载示例失败: ' + errMsg);
          return;
        }
      }

      message.destroy('example-loading');

      // Auto-select skill if example specifies one
      let exampleSkill: Skill | null = null;
      if (example.skillName && skillsList) {
        const matched = skillsList.find(s => s.name === example.skillName);
        if (matched) {
          exampleSkill = matched;
          setSelectedSkill(matched);
        }
      }

      // Auto-select database if example specifies one
      let matchedDb: DataSource | null = null;
      if (example.dbName && dataSources) {
        const found = dataSources.find((ds: DataSource) => ds.db_name === example.dbName);
        if (found) {
          matchedDb = found;
          setSelectedDb(found);
        }
      }

      // Transfer the single-flight ownership to the common send entry point.
      // No other browser event can interleave between this ref write and the
      // synchronous acquisition at the start of handleStart.
      exampleRunInFlightRef.current = false;
      await handleStart(translatedQuery, exampleSkill, matchedDb, exampleLegacyFile);
    } catch (err: unknown) {
      message.destroy('example-loading');
      console.error('Example click error:', err);
      const errMessage = err instanceof Error ? err.message : 'Unknown error';
      message.error('加载示例失败: ' + errMessage);
    } finally {
      exampleRunInFlightRef.current = false;
    }
  };

  // Clear chat history
  const handleClearChat = () => {
    cancelSummaryPresentation();
    setMessages([]);
    setConversationId(null);
    setQuery('');
    setExecutionMap({});
    setActiveMessageId(null);
    setActiveViewMsgId(null);
    setArtifacts([]);
    setRightPanelTab('preview');
    setStreamingSummary('');
    setSummaryComplete(false);
    sessionFiles.clearTurn();
    closeSessionFilePreview();
    setSelectedCitationIndex(null);
    setPendingFinalization(null);
    setPendingSummaryPresentation(null);
    router.push('/', undefined, { shallow: true });
  };

  const restoreFromHistory = (
    historyMessages: Array<{ role: string; context: string; order?: number; model_name?: string }>,
  ) => {
    cancelSummaryPresentation();
    setExecutionMap({});
    setActiveMessageId(null);
    setActiveViewMsgId(null);
    setActiveSubAgent(null);
    setArtifacts([]);
    setStreamingSummary('');
    setSummaryComplete(false);
    setSelectedCitationIndex(null);
    setPendingFinalization(null);
    setPendingSummaryPresentation(null);

    const newMessages: ChatMessage[] = [];
    const newExecutionMap: typeof executionMap = {};
    const allArtifacts: Artifact[] = [];
    const restoredSkillNames: Record<string, string> = {};

    historyMessages.forEach(msg => {
      if (msg.role === 'human') {
        newMessages.push({ id: generateUUID(), role: 'human', context: msg.context, order: msg.order });
      } else if (msg.role === 'view') {
        const viewId = generateUUID();
        let payload: any = null;
        try {
          payload = JSON.parse(msg.context);
        } catch {
          /* ignore parse failure */
        }

        if (payload && (payload.version === 1 || payload.version === 2) && payload.type === 'react-agent') {
          const steps: ExecutionStep[] = (payload.steps || []).map((s: any, idx: number) => ({
            id: s.id || `history-step-${idx}`,
            step: idx + 1,
            title: s.title || s.action || `Step ${idx + 1}`,
            detail: s.detail || '',
            status: (s.status === 'failed' ? 'failed' : 'done') as 'done' | 'failed',
            action: s.action,
            actionInput: s.action_input || undefined,
            todoMeta: s.todo_meta || undefined,
          }));

          const outputs: Record<string, ExecutionOutput[]> = {};
          const stepThoughts: Record<string, string> = {};
          const subAgents = restoreSubAgentStates(payload.sub_agents ?? payload.subAgents);

          (payload.steps || []).forEach((s: any, idx: number) => {
            const stepId = s.id || `history-step-${idx}`;
            if (Array.isArray(s.outputs)) {
              outputs[stepId] = s.outputs.map((o: any) => ({
                output_type: o.output_type || 'text',
                content: o.content,
              }));
            }
            if ((s.action === 'code_interpreter' || s.action === 'shell_interpreter') && s.action_input) {
              const existingOutputs = outputs[stepId] || [];
              const hasCode = existingOutputs.some((o: ExecutionOutput) => o.output_type === 'code');
              if (!hasCode) {
                try {
                  const input = typeof s.action_input === 'string' ? JSON.parse(s.action_input) : s.action_input;
                  if (input && input.code) {
                    outputs[stepId] = [{ output_type: 'code', content: input.code }, ...existingOutputs];
                  }
                } catch {
                  /* ignore */
                }
              }
            }
            const historyThought = buildActionDisplayText({
              actionIntention: s.action_intention,
              actionReason: s.action_reason,
              thought: s.thought,
            });
            if (historyThought) {
              stepThoughts[stepId] = historyThought;
            }
          });

          newExecutionMap[viewId] = {
            steps,
            outputs,
            activeStepId: steps.length > 0 ? steps[steps.length - 1].id : null,
            collapsed: false,
            stepThoughts,
            ...(Object.keys(subAgents).length > 0
              ? {
                  subAgents,
                  subAgentArtifacts: Object.values(subAgents).reduce(
                    (sum, agent) => sum + (agent.artifactCount || 0),
                    0,
                  ),
                }
              : {}),
          };

          const historyAnswer = decodeHistoryAnswer(payload);
          const finalContent = cleanFinalContent(historyAnswer.content);

          // History payload v2: the turn's input_files snapshot attaches to
          // the human message of this round. v1 stays on the legacy one-item
          // bridge (no snapshots, AttachmentMessageGroup falls back).
          if (payload.version === 2) {
            const attachedSnapshots = snapshotsFromInputFiles(payload.input_files);
            if (attachedSnapshots.length > 0) {
              const lastHuman = [...newMessages].reverse().find(m => m.role === 'human');
              if (lastHuman && !lastHuman.attachedFiles) {
                lastHuman.attachedFiles = attachedSnapshots;
              }
            }
          }

          const restoredArtifacts = buildArtifactsFromExecution(
            viewId,
            { steps, outputs, subAgents },
            finalContent,
            null,
          );
          allArtifacts.push(...restoredArtifacts);

          // Detect skill creation from restored execution
          const isSkillPackageStep = (s: ExecutionStep) => {
            if (s.action !== 'shell_interpreter') return false;
            const detailHas = s.detail?.includes('package_skill') || s.detail?.includes('init_skill');
            const inputHas = s.actionInput?.includes('package_skill') || s.actionInput?.includes('init_skill');
            const outputTexts = (outputs[s.id] || []).map(o => String(o.content)).join(' ');
            const outputHas =
              outputTexts.includes('package_skill') ||
              outputTexts.includes('init_skill') ||
              outputTexts.includes('Successfully packaged');
            return detailHas || inputHas || outputHas;
          };
          const skillStep = steps.find(isSkillPackageStep);
          if (skillStep) {
            const allText = [
              skillStep.actionInput || '',
              skillStep.detail || '',
              ...(outputs[skillStep.id] || []).map(o => String(o.content)),
            ].join(' ');
            const skillName = extractCreatedSkillName(allText);
            if (skillName) {
              restoredSkillNames[viewId] = skillName;
            }
          }

          newMessages.push({
            id: viewId,
            role: 'view',
            context: finalContent,
            citations: historyAnswer.citations,
            order: msg.order,
            thinking: false,
            taskPlan: Array.isArray(payload.task_plan)
              ? payload.task_plan
              : Array.isArray(payload.tasks)
                ? payload.tasks
                : undefined,
          });
        } else {
          const historyAnswer = decodeHistoryAnswer(msg.context || '');
          newMessages.push({
            id: viewId,
            role: 'view',
            context: cleanFinalContent(historyAnswer.content),
            citations: historyAnswer.citations,
            order: msg.order,
            thinking: false,
          });
        }
      }
    });

    setMessages(newMessages);
    setExecutionMap(newExecutionMap);
    setArtifacts(allArtifacts);
    if (Object.keys(restoredSkillNames).length > 0) {
      setCreatedSkillNames(prev => ({ ...prev, ...restoredSkillNames }));
    }

    const lastView = [...newMessages].reverse().find(m => m.role === 'view');
    if (lastView?.id) {
      setActiveMessageId(lastView.id);
      setStreamingSummary(lastView.context || '');
      setSummaryComplete(true);
      setSelectedCitationIndex(lastView.citations?.[0]?.index ?? null);
    }
  };

  const loadConversation = async (convUid: string) => {
    if (historyLoading) return;
    setHistoryLoading(true);
    try {
      const res: any = await axios.get(`/api/v1/chat/dialogue/messages/history?con_uid=${convUid}`);
      let msgList: any[] | null = null;
      if (res?.success && Array.isArray(res.data)) {
        msgList = res.data;
      } else if (Array.isArray(res?.data?.data)) {
        msgList = res.data.data;
      } else if (Array.isArray(res?.data)) {
        msgList = res.data;
      } else if (Array.isArray(res)) {
        msgList = res;
      }
      if (msgList && msgList.length > 0) {
        setConversationId(convUid);
        restoreFromHistory(
          msgList.map((m: any) => ({
            role: m.role,
            context: m.context,
            order: m.order,
            model_name: m.model_name,
          })),
        );
      }
    } catch (e) {
      console.error('Failed to load conversation', e);
      message.error('加载历史对话失败');
    } finally {
      setHistoryLoading(false);
    }
  };

  // Share current conversation — create share link and copy to clipboard
  const handleShare = async () => {
    if (!conversationId) {
      message.warning('请先开始一段对话再分享');
      return;
    }
    try {
      const res: any = await axios.post('/api/v1/chat/share', { conv_uid: conversationId });
      const shareUrl = res?.data?.share_url;
      if (!shareUrl) throw new Error('No share URL returned');
      const fullUrl = `${window.location.origin}${shareUrl}`;
      await navigator.clipboard.writeText(fullUrl);
      message.success('分享链接已复制到剪贴板！');
    } catch (e) {
      console.error('Failed to create share link', e);
      message.error('创建分享链接失败，请稍后重试');
    }
  };

  // Build snapshot of current conversation state for scheduled task creation
  const buildSnapshot = (): ChatReplayPayload => {
    // Prefer the payload actually sent to the agent this session — it carries
    // the real execution context (file_path / file_ids / database / knowledge /
    // skill / connectors) and is immune to UI state changed after sending.
    if (lastSentPayloadRef.current) {
      return lastSentPayloadRef.current;
    }
    // Fallback (e.g. conversation restored from history, where no send
    // happened this session): reconstruct from the first question + current
    // selections. Keeps the old behavior so this path never regresses.
    const firstUserMsg = messages.find(m => m.role === 'human');
    return {
      version: 1,
      user_input: firstUserMsg?.context ?? '',
      chat_mode: 'chat_react_agent',
      model_name: model,
      select_param: '',
      ext_info: {
        ...(selectedSkill ? { skill_id: selectedSkill.id, skill_name: selectedSkill.name } : {}),
        ...(selectedDb ? { database_name: selectedDb.db_name, database_type: selectedDb.db_type } : {}),
        ...(selectedKnowledge
          ? { knowledge_space_name: selectedKnowledge.name, knowledge_space_id: selectedKnowledge.id }
          : {}),
        ...(selectedConnectors.length > 0 ? { connector_ids: selectedConnectors.map(c => c.id) } : {}),
      },
    };
  };

  const _QuickAction = ({ icon, text, onClick }: { icon: any; text: string; onClick?: () => void }) => (
    <div
      onClick={onClick}
      className='flex items-center gap-2 px-4 py-2 bg-white dark:bg-[#2c2d31] border border-gray-200 dark:border-gray-700 rounded-full cursor-pointer hover:bg-gray-50 dark:hover:bg-[#35363a] transition-colors text-sm text-gray-600 dark:text-gray-300 shadow-sm'
    >
      {icon}
      <span>{text}</span>
    </div>
  );

  const getDbIcon = (type: string) => {
    const lowerType = type.toLowerCase();
    if (lowerType.includes('mysql')) return <ConsoleSqlOutlined className='text-blue-500' />;
    if (lowerType.includes('postgre')) return <DatabaseOutlined className='text-blue-400' />;
    if (lowerType.includes('mongo')) return <CloudServerOutlined className='text-green-500' />;
    if (lowerType.includes('sqlite')) return <DatabaseOutlined className='text-amber-500' />;
    return <DatabaseOutlined className='text-gray-500' />;
  };

  // Upload Props
  const uploadProps: any = {
    name: 'file',
    multiple: true,
    showUploadList: false,
    beforeUpload: (file: any) => {
      // Session-files flow: antd calls beforeUpload once per picked file; the
      // draft starts uploading immediately against the settled conversation
      // scope (violations render as blocked/error items in the rail). A staged
      // legacy example file must never mix with local uploads (file_path vs
      // file_ids), so the pick is refused before a draft is created.
      if (hasLegacyFile) {
        message.warning('示例文件与本地上传的附件不能混用，请先清除示例文件');
        return false;
      }
      void sessionFiles.addFiles([file as File], ensureSessionFilesConvId());
      return false; // Prevent auto upload, the session-files module owns it
    },
  };

  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#000000',
        },
      }}
    >
      <div className='flex h-full w-full bg-[#f7f7f9] dark:bg-[#0f1012] text-[#1a1b1e] dark:text-gray-200 font-sans overflow-hidden'>
        {/* Main Content */}
        <div className='flex-1 min-h-0 flex flex-col relative overflow-hidden bg-white dark:bg-[#111217]'>
          {/* Top Header */}
          <div className='h-16 flex-shrink-0 flex items-center justify-between px-8 border-b border-gray-200 dark:border-gray-800 bg-white/80 dark:bg-[#111217]/80 backdrop-blur z-20'>
            <div className='flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300 px-2 py-1 rounded-md'>
              <span>{t('home_title')}</span>
            </div>
            <div className='flex items-center gap-4'>
              {selectedDb && (
                <Tag className='flex items-center gap-1 bg-blue-50 border-blue-200 text-blue-700 px-3 py-1 rounded-full text-xs'>
                  {getDbIcon(selectedDb.type)} <span className='font-medium ml-1'>{selectedDb.db_name}</span>
                </Tag>
              )}
              {messages.length > 0 && (
                <Button type='text' size='small' onClick={handleClearChat} className='text-gray-500'>
                  Clear Chat
                </Button>
              )}
              <BellOutlined className='text-lg text-gray-500 cursor-pointer' />
              <div className='flex items-center gap-2 bg-gray-100 dark:bg-gray-800 px-3 py-1 rounded-full text-xs font-medium'>
                <ThunderboltOutlined className='text-yellow-500' /> <span>300</span>
              </div>
              <Avatar size='small' icon={<UserOutlined />} className='bg-blue-500' />
            </div>
          </div>

          {/* From Task Banner - shown when navigating from a scheduled task */}
          {router.query.from_task && <FromTaskBanner taskId={router.query.from_task as string} />}

          {/* Chat Messages or Hero Section */}
          {/* When from_task mode and loading history, show loading spinner instead of Hero */}
          {router.query.from_task && historyLoading && messages.length === 0 ? (
            <div className='flex-1 flex items-center justify-center'>
              <Spin size='large' tip='加载对话历史...' />
            </div>
          ) : messages.length > 0 ? (
            <div className={`flex-1 min-h-0 flex overflow-hidden ${rightPanelCollapsed ? 'justify-center' : ''}`}>
              <div
                className={`${rightPanelCollapsed ? 'flex-1 max-w-[800px] border-r-0' : 'flex-[2] min-w-0 border-r border-gray-200/80 dark:border-gray-800'} min-h-0 flex flex-col overflow-hidden bg-white dark:bg-[#111217] transition-all duration-300 relative`}
              >
                <div className='flex-1 min-h-0 overflow-y-auto'>
                  {rounds.map((round, roundIndex) => {
                    const isLastRound = roundIndex === rounds.length - 1;
                    const isSelected = round.viewMsg?.id === selectedViewMsgId;
                    const isCurrentRoundCollapsed = !isLastRound && !isSelected;

                    const execution = round.viewMsg?.id ? executionMap[round.viewMsg.id] : undefined;
                    const {
                      sections,
                      activeStep: _activeStep,
                      outputs: _outputs,
                      stepThoughts,
                    } = convertToManusFormat(execution, round.humanMsg?.context, t);
                    const isWorking =
                      (isLastRound &&
                        (round.viewMsg?.thinking || execution?.steps.some(s => s.status === 'running'))) ||
                      false;

                    const isPresentingThisRound = summaryPresentationResponseId === round.viewMsg?.id;
                    const roundAssistantText = isPresentingThisRound
                      ? streamingSummary
                      : round.viewMsg?.context || undefined;
                    const roundCitations = round.viewMsg?.citations || [];

                    return (
                      <ManusLeftPanel
                        key={round.viewMsg?.id || round.humanMsg?.id || `round-${roundIndex}`}
                        sections={sections}
                        subAgentSlot={
                          execution?.subAgents && Object.keys(execution.subAgents).length > 0 ? (
                            <SubAgentSection
                              subAgents={execution.subAgents}
                              artifactCount={execution.subAgentArtifacts}
                              activeSubAgentId={
                                isSelected && activeSubAgent && activeSubAgent.messageId === round.viewMsg?.id
                                  ? activeSubAgent.agentId
                                  : null
                              }
                              onSubAgentClick={agentId => {
                                if (round.viewMsg?.id) {
                                  setActiveViewMsgId(round.viewMsg.id);
                                  setActiveSubAgent({ messageId: round.viewMsg.id, agentId });
                                }
                                setRightPanelView('execution');
                                setRightPanelCollapsed(false);
                              }}
                            />
                          ) : undefined
                        }
                        activeStepId={isSelected ? selectedStepId || execution?.activeStepId : undefined}
                        onStepClick={(stepId, _sectionId) => {
                          if (round.viewMsg?.id) {
                            setActiveViewMsgId(round.viewMsg.id);
                            setSelectedStepId(stepId);
                            // Clicking a main-agent step exits the sub-agent
                            // process view, so the right panel shows this step.
                            setActiveSubAgent(null);
                            setRightPanelView('execution');
                            setRightPanelCollapsed(false);
                            setExecutionMap(prev => ({
                              ...prev,
                              [round.viewMsg!.id!]: {
                                ...prev[round.viewMsg!.id!],
                                activeStepId: stepId,
                              },
                            }));
                          }
                        }}
                        isWorking={isWorking}
                        userQuery={round.humanMsg?.context}
                        attachedFiles={round.humanMsg?.attachedFiles}
                        attachedKnowledge={round.humanMsg?.attachedKnowledge}
                        attachedSkill={round.humanMsg?.attachedSkill}
                        attachedDb={round.humanMsg?.attachedDb}
                        taskPlan={round.viewMsg?.taskPlan}
                        attachedConnectors={round.humanMsg?.attachedConnectors}
                        assistantText={roundAssistantText}
                        isAssistantStreaming={isPresentingThisRound && !_summaryComplete}
                        citationIndexes={roundCitations.map(citation => citation.index)}
                        onReferencesClick={
                          roundCitations.length > 0
                            ? () => {
                                if (round.viewMsg?.id) setActiveViewMsgId(round.viewMsg.id);
                                setSelectedCitationIndex(roundCitations[0].index);
                                setRightPanelView('references');
                                setRightPanelCollapsed(false);
                              }
                            : undefined
                        }
                        modelName={round.viewMsg?.model_name || model}
                        stepThoughts={stepThoughts}
                        artifacts={artifacts.filter(a => a.messageId === round.viewMsg?.id)}
                        onArtifactClick={artifact => {
                          if (round.viewMsg?.id) setActiveViewMsgId(round.viewMsg.id);
                          setRightPanelCollapsed(false);
                          if (artifact.type === 'html') {
                            setPreviewArtifact(artifact as Artifact);
                            setRightPanelView('html-preview');
                          } else if (artifact.type === 'code' && artifact.stepId) {
                            setSelectedStepId(artifact.stepId);
                            setRightPanelView('execution');
                            if (round.viewMsg?.id && execution) {
                              setExecutionMap(prev => ({
                                ...prev,
                                [round.viewMsg!.id!]: {
                                  ...prev[round.viewMsg!.id!],
                                  activeStepId: artifact.stepId!,
                                },
                              }));
                            }
                          } else if (artifact.type === 'file') {
                            // Image file artifacts: preview instead of download
                            if (/\.(png|jpg|jpeg|gif|webp|svg|bmp)$/i.test(artifact.name)) {
                              setPreviewArtifact(artifact as Artifact);
                              setRightPanelView('image-preview');
                            } else {
                              downloadArtifact(artifact as Artifact);
                            }
                          } else if (artifact.type === 'image') {
                            setPreviewArtifact(artifact as Artifact);
                            setRightPanelView('image-preview');
                          }
                        }}
                        onArtifactDownload={artifact => downloadArtifact(artifact as Artifact)}
                        onViewAllFiles={() => {
                          if (round.viewMsg?.id) setActiveViewMsgId(round.viewMsg.id);
                          setRightPanelCollapsed(false);
                          setRightPanelView('files');
                        }}
                        isCollapsed={isCurrentRoundCollapsed}
                        onExpand={() => {
                          if (round.viewMsg?.id) setActiveViewMsgId(round.viewMsg.id);
                        }}
                        createdSkillName={createdSkillNames[round.viewMsg?.id || '']}
                        onSkillCardClick={_skillName => {
                          if (round.viewMsg?.id) setActiveViewMsgId(round.viewMsg.id);
                          setRightPanelCollapsed(false);
                          setRightPanelView('skill-preview');
                          // Find the package_skill step and select it so right panel shows SkillCardRenderer
                          if (execution) {
                            const skillStep = execution.steps.find((s: ExecutionStep) => {
                              if (s.action !== 'shell_interpreter') return false;
                              const detailHas = s.detail?.includes('package_skill') || s.detail?.includes('init_skill');
                              const inputHas =
                                s.actionInput?.includes('package_skill') || s.actionInput?.includes('init_skill');
                              const outputTexts = (execution.outputs[s.id] || []).map(o => String(o.content)).join(' ');
                              const outputHas =
                                outputTexts.includes('package_skill') ||
                                outputTexts.includes('init_skill') ||
                                outputTexts.includes('Successfully packaged');
                              return detailHas || inputHas || outputHas;
                            });
                            if (skillStep) {
                              setSelectedStepId(skillStep.id);
                              setExecutionMap(prev => ({
                                ...prev,
                                [round.viewMsg!.id!]: { ...prev[round.viewMsg!.id!], activeStepId: skillStep.id },
                              }));
                            }
                          }
                        }}
                        onSkillDownload={async skillName => {
                          try {
                            const base = process.env.API_BASE_URL || '';
                            const res = await fetch(
                              `${base}/api/v1/agent/skills/download?skill_name=${encodeURIComponent(skillName)}`,
                            );
                            if (!res.ok) throw new Error('Download failed');
                            const blob = await res.blob();
                            const url = URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = `${skillName}.zip`;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            URL.revokeObjectURL(url);
                          } catch {
                            // Download failed silently
                          }
                        }}
                      />
                    );
                  })}
                </div>

                {/* Input Area at Bottom for Chat Mode - Hidden in read-only task replay mode */}
                {!router.query.from_task && (
                  <div className='bg-gradient-to-t from-white via-white/95 to-white/80 dark:from-[#1a1b1e] dark:via-[#1a1b1e]/95 dark:to-[#1a1b1e]/80 p-4 md:p-6'>
                    <div className='max-w-[720px] mx-auto'>
                      {/* Context Tags Area */}
                      <div className='flex flex-wrap gap-2 mb-2'>
                        {selectedDb && (
                          <Tag
                            closable
                            onClose={() => setSelectedDb(null)}
                            className='flex items-center gap-1 bg-blue-50 border-blue-200 text-blue-700 px-3 py-1 rounded-full'
                          >
                            {getDbIcon(selectedDb.type)} <span className='font-medium ml-1'>{selectedDb.db_name}</span>
                          </Tag>
                        )}
                        {selectedKnowledge && (
                          <Tag
                            closable
                            onClose={() => setSelectedKnowledge(null)}
                            className='flex items-center gap-1 bg-orange-50 border-orange-200 text-orange-700 px-3 py-1 rounded-full'
                          >
                            <BookOutlined /> <span className='font-medium ml-1'>{selectedKnowledge.name}</span>
                          </Tag>
                        )}
                        {selectedConnectors.length > 0 && (
                          <>
                            {selectedConnectors.map(c => (
                              <Tag
                                key={c.id}
                                closable
                                onClose={() => setSelectedConnectors(prev => prev.filter(s => s.id !== c.id))}
                                className='flex items-center gap-1 bg-violet-50 border-violet-200 text-violet-700 px-3 py-1 rounded-full'
                              >
                                <ApiOutlined /> <span className='font-medium ml-1'>{c.display_name}</span>
                              </Tag>
                            ))}
                          </>
                        )}
                      </div>

                      {/* Human-in-the-loop Question Dock */}
                      {pendingQuestion && (
                        <div className='mb-3 w-full'>
                          <QuestionDock
                            request={{
                              request_id: pendingQuestion.request_id,
                              conv_id: pendingQuestion.conv_id,
                              questions: pendingQuestion.questions,
                            }}
                            onReply={replyQuestion}
                            onReject={rejectQuestion}
                          />
                        </div>
                      )}

                      {/* Outer Frame - Floating Effect */}
                      <div
                        className='rounded-2xl w-full relative transition-all duration-300 shadow-[0_12px_32px_rgba(0,0,0,0.1),0_4px_12px_rgba(0,0,0,0.06)] hover:shadow-[0_20px_48px_rgba(0,0,0,0.16),0_8px_24px_rgba(0,0,0,0.08)] dark:shadow-[0_12px_32px_rgba(0,0,0,0.4)] dark:hover:shadow-[0_20px_48px_rgba(0,0,0,0.5)]'
                        {...composerDragHandlers}
                      >
                        {composerDragOverlay}
                        {/* White Inner Box - Clean Glass Card */}
                        <div className='bg-white/95 backdrop-blur-md dark:bg-[#1e1f24]/95 rounded-2xl border border-gray-100 dark:border-[#33353b] shadow-[inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] p-3 px-4'>
                          <AttachmentRail
                            drafts={sessionFiles.files}
                            legacyFiles={sessionFiles.legacyFile ? [sessionFiles.legacyFile] : []}
                            onRemove={sessionFiles.remove}
                            onRetry={() => sessionFiles.retryFailed()}
                            onPreview={openSessionFilePreview}
                            onLegacyPreview={openLegacyFilePreview}
                            onClearAll={clearComposerAttachments}
                            density='compact'
                            addControl={
                              <Upload {...uploadProps}>
                                <AttachmentRailCompactAddButton />
                              </Upload>
                            }
                            preview={showInlineAttachmentPreview ? null : sessionFilePreview}
                            onClosePreview={closeSessionFilePreview}
                            className='mb-2'
                          />
                          {taskPlan.length > 0 && (
                            <div className='mb-3'>
                              <TaskPlanCard tasks={taskPlan} embedded />
                            </div>
                          )}
                          <Input.TextArea
                            value={query}
                            onChange={e => {
                              const newValue = e.target.value;
                              setQuery(newValue);
                              if (newValue === '/' && !isSkillPanelOpen && !selectedSkill) {
                                setIsSkillPanelOpen(true);
                              }
                            }}
                            onPressEnter={e => {
                              if (!e.shiftKey) {
                                e.preventDefault();
                                handleStart();
                              }
                            }}
                            placeholder={
                              t('ask_data_question') ||
                              'Ask a question about your database, upload a CSV, or generate a report...'
                            }
                            autoSize={{ minRows: 2, maxRows: 6 }}
                            className='flex-1 resize-none !border-none !shadow-none !bg-transparent px-0 py-2'
                            style={{ backgroundColor: 'transparent' }}
                          />

                          {/* Toolbar Row */}
                          <div className='flex items-center justify-between mt-1'>
                            <div className='flex items-center gap-3'>
                              {/* Add Button */}
                              <Dropdown
                                menu={{
                                  items: [
                                    {
                                      key: 'upload',
                                      label: (
                                        <Upload {...uploadProps}>
                                          <div className='w-full'>Upload File</div>
                                        </Upload>
                                      ),
                                      icon: <UploadOutlined />,
                                    },
                                    {
                                      key: 'database',
                                      label: 'Select Data Source',
                                      icon: <DatabaseOutlined />,
                                      onClick: () => setIsDbModalOpen(true),
                                    },
                                    {
                                      key: 'knowledge',
                                      label: 'Select Knowledge Base',
                                      icon: <BookOutlined />,
                                      onClick: () => setIsKnowledgeModalOpen(true),
                                    },
                                    {
                                      key: 'connector',
                                      label: t('use_connector'),
                                      icon: <ApiOutlined />,
                                      onClick: () => setIsConnectorPanelOpen(true),
                                    },
                                  ],
                                }}
                                trigger={['click']}
                              >
                                <Tooltip title={t('add_context')}>
                                  <Button
                                    type='text'
                                    shape='circle'
                                    size='small'
                                    icon={<PlusOutlined />}
                                    className='flex items-center justify-center text-gray-500 hover:text-violet-600 bg-gradient-to-b from-white to-gray-50 dark:from-[#2a2b2f] dark:to-[#1e1f24] dark:text-gray-300 border border-gray-200/80 dark:border-white/10 shadow-[0_1px_2px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.05)] hover:-translate-y-[0.5px] hover:shadow-[0_2px_4px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,1)] dark:hover:border-white/20 transition-all flex-shrink-0'
                                  />
                                </Tooltip>
                              </Dropdown>

                              {/* Skill Selector Button with Badge */}
                              <Popover
                                trigger='click'
                                placement='topLeft'
                                open={isSkillPanelOpen}
                                onOpenChange={setIsSkillPanelOpen}
                                overlayClassName='manus-skill-menu'
                                overlayInnerStyle={{ padding: 0, borderRadius: 12 }}
                                content={
                                  <div className='w-[320px] bg-white dark:bg-[#2c2d31] rounded-xl shadow-xl overflow-hidden'>
                                    <div className='p-3 border-b border-gray-100 dark:border-gray-700'>
                                      <Input
                                        placeholder={t('search_skill')}
                                        prefix={<SearchOutlined className='text-gray-400' />}
                                        value={skillSearchQuery}
                                        onChange={e => setSkillSearchQuery(e.target.value)}
                                        className='rounded-lg'
                                        allowClear
                                        size='small'
                                      />
                                    </div>
                                    <div className='max-h-[300px] overflow-y-auto'>
                                      {(skillsList || [])
                                        .filter(
                                          skill =>
                                            !skillSearchQuery ||
                                            skill.name.toLowerCase().includes(skillSearchQuery.toLowerCase()) ||
                                            skill.description.toLowerCase().includes(skillSearchQuery.toLowerCase()),
                                        )
                                        .map(skill => (
                                          <div
                                            key={skill.id}
                                            onClick={() => {
                                              if (selectedSkill?.id === skill.id) {
                                                setSelectedSkill(null);
                                                setQuery('');
                                              } else {
                                                setSelectedSkill(skill);
                                                setQuery(`/${skill.name} `);
                                              }
                                              setIsSkillPanelOpen(false);
                                              setSkillSearchQuery('');
                                            }}
                                            className={`flex items-start gap-3 px-3 py-2.5 cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-800 ${
                                              selectedSkill?.id === skill.id ? 'bg-purple-50 dark:bg-purple-900/20' : ''
                                            }`}
                                          >
                                            <div className='flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-white text-xs'>
                                              {skill.icon || <ThunderboltOutlined />}
                                            </div>
                                            <div className='flex-1 min-w-0'>
                                              <div className='flex items-center gap-2'>
                                                <span className='font-medium text-sm text-gray-800 dark:text-gray-200'>
                                                  {skill.name}
                                                </span>
                                                <span
                                                  className={`text-[10px] px-1.5 py-0.5 rounded ${
                                                    skill.type === 'official'
                                                      ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
                                                      : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                                                  }`}
                                                >
                                                  {skill.type === 'official'
                                                    ? t('picker_skill_official')
                                                    : t('picker_skill_personal')}
                                                </span>
                                              </div>
                                              <p className='text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2'>
                                                {skill.description}
                                              </p>
                                            </div>
                                            {selectedSkill?.id === skill.id && (
                                              <CheckCircleFilled className='text-purple-500 flex-shrink-0 text-sm' />
                                            )}
                                          </div>
                                        ))}
                                      {(skillsList || []).filter(
                                        skill =>
                                          !skillSearchQuery ||
                                          skill.name.toLowerCase().includes(skillSearchQuery.toLowerCase()) ||
                                          skill.description.toLowerCase().includes(skillSearchQuery.toLowerCase()),
                                      ).length === 0 && (
                                        <div className='text-center py-8 text-gray-400'>
                                          <ThunderboltOutlined className='text-2xl mb-2 opacity-50' />
                                          <div className='text-xs'>
                                            {skillSearchQuery ? t('picker_skill_no_match') : t('picker_skill_empty')}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                    <div className='border-t border-gray-100 dark:border-gray-700 px-3 py-2 flex items-center justify-between bg-gray-50/50 dark:bg-gray-900/50'>
                                      <span className='text-[10px] text-gray-400'>
                                        {t('picker_skill_count', { count: (skillsList || []).length })}
                                      </span>
                                      <Button
                                        type='link'
                                        size='small'
                                        onClick={() => {
                                          router.push('/construct/skills');
                                          setIsSkillPanelOpen(false);
                                        }}
                                        className='text-[10px] p-0 h-auto'
                                      >
                                        {t('picker_manage_skill')}
                                      </Button>
                                    </div>
                                  </div>
                                }
                              >
                                <Tooltip
                                  title={
                                    selectedSkill
                                      ? t('skill_selected', { name: selectedSkill.name })
                                      : t('select_skill')
                                  }
                                >
                                  <Button
                                    type='text'
                                    shape='circle'
                                    size='small'
                                    className={`relative flex items-center justify-center flex-shrink-0 transition-all ${
                                      selectedSkill
                                        ? 'bg-gradient-to-br from-[#a78bfa] to-[#7c3aed] text-white border border-transparent shadow-[0_2px_4px_rgba(139,92,246,0.3),inset_0_1px_0_rgba(255,255,255,0.3)] hover:-translate-y-[0.5px] hover:shadow-[0_4px_8px_rgba(139,92,246,0.4),inset_0_1px_0_rgba(255,255,255,0.3)]'
                                        : 'text-gray-500 hover:text-violet-600 bg-gradient-to-b from-white to-gray-50 dark:from-[#2a2b2f] dark:to-[#1e1f24] dark:text-gray-300 border border-gray-200/80 dark:border-white/10 shadow-[0_1px_2px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.05)] hover:-translate-y-[0.5px] hover:shadow-[0_2px_4px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,1)] dark:hover:border-white/20'
                                    }`}
                                  >
                                    <div className='relative'>
                                      <ThunderboltOutlined className={selectedSkill ? 'text-white' : ''} />
                                      {selectedSkill && (
                                        <span className='absolute -top-1.5 -right-1.5 bg-white text-[#7c3aed] text-[8px] rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold shadow-sm ring-1 ring-[#7c3aed]/30'>
                                          1
                                        </span>
                                      )}
                                    </div>
                                  </Button>
                                </Tooltip>
                              </Popover>

                              {/* Connector Selector Button */}
                              <Popover
                                trigger='click'
                                placement='topLeft'
                                open={isConnectorPanelOpen}
                                onOpenChange={setIsConnectorPanelOpen}
                                overlayClassName='manus-skill-menu'
                                overlayInnerStyle={{ padding: 0, borderRadius: 12 }}
                                content={
                                  <div className='w-[320px] bg-white dark:bg-[#2c2d31] rounded-xl shadow-xl overflow-hidden'>
                                    <div className='p-3 border-b border-gray-100 dark:border-gray-700'>
                                      <Input
                                        placeholder={t('search_connector')}
                                        prefix={<SearchOutlined className='text-gray-400' />}
                                        value={connectorSearchQuery}
                                        onChange={e => setConnectorSearchQuery(e.target.value)}
                                        className='rounded-lg'
                                        allowClear
                                        size='small'
                                      />
                                    </div>
                                    <div className='max-h-[300px] overflow-y-auto'>
                                      {(connectorsList || [])
                                        .filter(
                                          (c: ConnectorInstance) =>
                                            c.status === 'active' &&
                                            (!connectorSearchQuery ||
                                              c.display_name
                                                .toLowerCase()
                                                .includes(connectorSearchQuery.toLowerCase()) ||
                                              c.connector_type
                                                .toLowerCase()
                                                .includes(connectorSearchQuery.toLowerCase())),
                                        )
                                        .map((c: ConnectorInstance) => (
                                          <div
                                            key={c.id}
                                            onClick={() => {
                                              setSelectedConnectors(prev =>
                                                prev.some(s => s.id === c.id)
                                                  ? prev.filter(s => s.id !== c.id)
                                                  : [...prev, c],
                                              );
                                              setConnectorSearchQuery('');
                                            }}
                                            className={`flex items-start gap-3 px-3 py-2.5 cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-800 ${
                                              selectedConnectors.some(s => s.id === c.id)
                                                ? 'bg-violet-50 dark:bg-violet-900/20'
                                                : ''
                                            }`}
                                          >
                                            <div className='flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center text-white text-xs'>
                                              <ApiOutlined />
                                            </div>
                                            <div className='flex-1 min-w-0'>
                                              <div className='flex items-center gap-2'>
                                                <span className='font-medium text-sm text-gray-800 dark:text-gray-200'>
                                                  {c.display_name}
                                                </span>
                                                <span className='text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'>
                                                  {t('picker_connector_active')}
                                                </span>
                                              </div>
                                              <p
                                                className='text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate'
                                                title={(c.config?.description as string) || c.connector_type}
                                              >
                                                {(c.config?.description as string) || c.connector_type}
                                              </p>
                                            </div>
                                            {selectedConnectors.some(s => s.id === c.id) && (
                                              <CheckCircleFilled className='text-violet-500 flex-shrink-0 text-sm' />
                                            )}
                                          </div>
                                        ))}
                                      {(connectorsList || []).filter(
                                        (c: ConnectorInstance) =>
                                          c.status === 'active' &&
                                          (!connectorSearchQuery ||
                                            c.display_name.toLowerCase().includes(connectorSearchQuery.toLowerCase()) ||
                                            c.connector_type
                                              .toLowerCase()
                                              .includes(connectorSearchQuery.toLowerCase())),
                                      ).length === 0 && (
                                        <div className='text-center py-8 text-gray-400'>
                                          <ApiOutlined className='text-2xl mb-2 opacity-50' />
                                          <div className='text-xs'>
                                            {connectorSearchQuery
                                              ? t('picker_connector_no_match')
                                              : t('picker_connector_empty')}
                                          </div>
                                        </div>
                                      )}
                                    </div>
                                    <div className='border-t border-gray-100 dark:border-gray-700 px-3 py-2 flex items-center justify-between bg-gray-50/50 dark:bg-gray-900/50'>
                                      <span className='text-[10px] text-gray-400'>
                                        {t('picker_connector_count', {
                                          count: (connectorsList || []).filter(
                                            (c: ConnectorInstance) => c.status === 'active',
                                          ).length,
                                        })}
                                      </span>
                                      <Button
                                        type='link'
                                        size='small'
                                        onClick={() => {
                                          router.push('/construct/connectors');
                                          setIsConnectorPanelOpen(false);
                                        }}
                                        className='text-[10px] p-0 h-auto'
                                      >
                                        {t('picker_manage_connector')}
                                      </Button>
                                    </div>
                                  </div>
                                }
                              >
                                <Tooltip
                                  title={
                                    selectedConnectors.length === 0
                                      ? t('select_mcp')
                                      : selectedConnectors.length === 1
                                        ? t('connector_selected', { name: selectedConnectors[0].display_name })
                                        : t('connectors_selected', {
                                            count: selectedConnectors.length,
                                            names: selectedConnectors.map(c => c.display_name).join('、'),
                                          })
                                  }
                                >
                                  <Button
                                    type='text'
                                    shape='circle'
                                    size='small'
                                    className={`relative flex items-center justify-center flex-shrink-0 transition-all ${
                                      selectedConnectors.length > 0
                                        ? 'bg-gradient-to-br from-[#8b5cf6] to-[#6366f1] text-white border border-transparent shadow-[0_2px_4px_rgba(139,92,246,0.3),inset_0_1px_0_rgba(255,255,255,0.3)] hover:-translate-y-[0.5px] hover:shadow-[0_4px_8px_rgba(139,92,246,0.4),inset_0_1px_0_rgba(255,255,255,0.3)]'
                                        : 'text-gray-500 hover:text-violet-600 bg-gradient-to-b from-white to-gray-50 dark:from-[#2a2b2f] dark:to-[#1e1f24] dark:text-gray-300 border border-gray-200/80 dark:border-white/10 shadow-[0_1px_2px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.05)] hover:-translate-y-[0.5px] hover:shadow-[0_2px_4px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,1)] dark:hover:border-white/20'
                                    }`}
                                  >
                                    <div className='relative'>
                                      <ApiOutlined className={selectedConnectors.length > 0 ? 'text-white' : ''} />
                                      {selectedConnectors.length > 0 && (
                                        <span className='absolute -top-1.5 -right-1.5 bg-white text-violet-600 text-[8px] rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold shadow-sm ring-1 ring-violet-500/30'>
                                          {selectedConnectors.length}
                                        </span>
                                      )}
                                    </div>
                                  </Button>
                                </Tooltip>
                              </Popover>

                              {/* Separator dot */}
                              <div className='w-px h-4 bg-gray-200 dark:bg-gray-700 mx-0.5' />

                              {/* Model Selector with premium styling */}
                              <div className='model-selector-premium'>
                                <ModelSelector onChange={val => setModel(val)} />
                              </div>
                              <style
                                dangerouslySetInnerHTML={{
                                  __html: `
                                  .model-selector-premium .ant-select { border-radius: 8px !important; border: none !important; }
                                  .model-selector-premium .ant-select-selector { background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%) !important; border: 1px solid rgba(0,0,0,0.12) !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,1) !important; border-radius: 8px !important; transition: all 0.2s ease !important; padding: 0 8px !important; }
                                  .dark .model-selector-premium .ant-select-selector { background: linear-gradient(180deg, #2a2b2f 0%, #1e1f24 100%) !important; border: 1px solid rgba(255,255,255,0.1) !important; box-shadow: 0 1px 2px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.05) !important; }
                                  .model-selector-premium .ant-select:hover .ant-select-selector { border-color: rgba(0,0,0,0.2) !important; box-shadow: 0 2px 4px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,1) !important; transform: translateY(-0.5px); }
                                  .dark .model-selector-premium .ant-select:hover .ant-select-selector { border-color: rgba(255,255,255,0.15) !important; }
                                  .model-selector-premium .ant-select-focused .ant-select-selector { border-color: #a78bfa !important; box-shadow: 0 0 0 2px rgba(167,139,250,0.15), inset 0 1px 0 rgba(255,255,255,1) !important; }
                                  .dark .model-selector-premium .ant-select-focused .ant-select-selector { box-shadow: 0 0 0 2px rgba(167,139,250,0.2), inset 0 1px 0 rgba(255,255,255,0.05) !important; }
                                  
                                  /* Global Dropdown Item Styles for Model Selectors */
                                  .ant-select-dropdown .ant-select-item-option-selected { background-color: #f1f5f9 !important; color: #0f172a !important; font-weight: 500 !important; }
                                  .ant-select-dropdown .ant-select-item-option-active:not(.ant-select-item-option-selected) { background-color: #f8fafc !important; }
                                  .dark .ant-select-dropdown .ant-select-item-option-selected { background-color: rgba(255,255,255,0.08) !important; color: #e2e8f0 !important; }
                                  .dark .ant-select-dropdown .ant-select-item-option-active:not(.ant-select-item-option-selected) { background-color: rgba(255,255,255,0.04) !important; }
                                `,
                                }}
                              />
                            </div>

                            <div className='flex items-center gap-2.5'>
                              {contextStatus && (
                                <ContextUsageBar
                                  used={contextStatus.used_tokens}
                                  budget={contextStatus.max_tokens}
                                  ratio={contextStatus.usage_percent / 100}
                                  state={contextStatus.state}
                                  compactLayer={contextStatus.layer}
                                  variant='compact'
                                  className='mr-0.5'
                                />
                              )}

                              {/* Voice Button */}
                              <Tooltip title={t('voice_input')}>
                                <Button
                                  type='text'
                                  shape='circle'
                                  icon={<AudioOutlined className='text-gray-500 text-[18px]' />}
                                  onClick={() => message.info(t('voice_input_coming_soon'))}
                                  className='flex-shrink-0 h-9 w-9 transition-all duration-200 flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-800'
                                />
                              </Tooltip>

                              {/* Send Button with blue gradient + gloss animation.
                                  While a reply is streaming it becomes a stop button. */}
                              {loading && !queuedSendAfterUpload ? (
                                // Stop button — same shape/color family as the send button
                                // (ChatGPT/Claude pattern): blue gradient circle carrying a
                                // white rounded-square stop glyph. Native <button> keeps
                                // antd's primary-button hover overrides out of the way.
                                <button
                                  type='button'
                                  aria-label={t('stop_generating')}
                                  onClick={handleStopGeneration}
                                  className='relative flex-shrink-0 h-9 w-9 rounded-full flex items-center justify-center shadow-lg transition-all duration-200 hover:shadow-blue-300/40 hover:shadow-xl hover:scale-105'
                                  style={{ background: 'linear-gradient(135deg, #3b82f6, #2563eb)' }}
                                >
                                  <span className='h-3 w-3 rounded-[3px] bg-white' />
                                </button>
                              ) : (
                                <Button
                                  type='primary'
                                  shape={queuedSendAfterUpload ? 'round' : 'circle'}
                                  icon={queuedSendAfterUpload ? undefined : <ArrowUpOutlined />}
                                  onClick={() => handleStart()}
                                  disabled={
                                    (!query.trim() && !hasSessionFileDrafts && !hasLegacyFile) ||
                                    loading ||
                                    queuedSendAfterUpload
                                  }
                                  loading={queuedSendAfterUpload}
                                  className={`group/send relative overflow-hidden border-none shadow-lg flex-shrink-0 h-9 transition-all duration-200 ${
                                    queuedSendAfterUpload ? 'px-4' : 'w-9'
                                  } ${
                                    query.trim() || hasSessionFileDrafts || hasLegacyFile
                                      ? 'bg-gradient-to-br from-[#3b82f6] to-[#2563eb] hover:shadow-blue-300/40 hover:shadow-xl hover:scale-105'
                                      : 'bg-gray-200 text-gray-400'
                                  }`}
                                  style={
                                    query.trim() || hasSessionFileDrafts || hasLegacyFile
                                      ? { background: 'linear-gradient(135deg, #3b82f6, #2563eb)' }
                                      : undefined
                                  }
                                >
                                  {queuedSendAfterUpload && <span className='text-[13px] font-medium'>上传后发送</span>}
                                  {(query.trim() || hasSessionFileDrafts || hasLegacyFile) && (
                                    <span
                                      className='absolute inset-0 opacity-0 group-hover/send:opacity-100 transition-opacity duration-300 pointer-events-none'
                                      style={{
                                        background:
                                          'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.25) 45%, rgba(255,255,255,0.35) 50%, rgba(255,255,255,0.25) 55%, transparent 60%)',
                                        animation: 'glossSweepChat 1.8s ease-in-out infinite',
                                      }}
                                    />
                                  )}
                                </Button>
                              )}
                            </div>
                            <style
                              dangerouslySetInnerHTML={{
                                __html: `@keyframes glossSweepChat { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }`,
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
              {/* Panel toggle handle — placed between panels to avoid overflow clipping */}
              <div className='relative z-20 flex-shrink-0'>
                <Tooltip title={rightPanelCollapsed ? t('expand_panel') : t('collapse_panel')} placement='left'>
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
              <div
                className={`${rightPanelCollapsed ? 'w-0 min-w-0 overflow-hidden opacity-0' : 'flex-[3] min-w-0 overflow-hidden'} min-h-0 bg-[#f8f8fb] dark:bg-[#0f1114] flex flex-col transition-all duration-300`}
              >
                {showInlineAttachmentPreview ? (
                  <div className='flex-1 min-h-0 flex flex-col bg-white dark:bg-[#1a1b1e]'>
                    <div className='flex h-12 flex-shrink-0 items-center justify-between border-b border-slate-200/80 bg-white/95 px-3 dark:border-white/10 dark:bg-[#1a1b1e]/95'>
                      <AttachmentPreviewPanelTitle />
                      <AttachmentPreviewCloseButton onClose={closeSessionFilePreview} />
                    </div>
                    <div className='flex-1 overflow-y-auto p-3'>{renderSessionFilePreviewBody()}</div>
                  </div>
                ) : (
                  (() => {
                    const activeViewMsg = messages.find(m => m.id === selectedViewMsgId && m.role === 'view');
                    const rawExecution = activeViewMsg?.id ? executionMap[activeViewMsg.id] : undefined;
                    // Respect user's manual step selection for the right panel
                    const execution =
                      rawExecution && selectedStepId ? { ...rawExecution, activeStepId: selectedStepId } : rawExecution;
                    const _converted = convertToManusFormat(execution, undefined, t);
                    let activeStep = _converted.activeStep;
                    let outputs = _converted.outputs;
                    let isRunning = execution?.steps.some(s => s.status === 'running') || false;

                    // Devin-style sub-agent process view: when a sub-agent is
                    // selected, override activeStep/outputs with that sub-agent's
                    // step list (reusing the execution view's rendering).
                    // Guard on messageId so a stale selection from another round
                    // cannot leak a same-id sub-agent into this round's view.
                    const activeSub =
                      activeSubAgent && activeSubAgent.messageId === activeViewMsg?.id
                        ? execution?.subAgents?.[activeSubAgent.agentId]
                        : undefined;
                    const activeDispatchStepId =
                      _converted.activeStep?.action === 'dispatch_parallel_tasks' ? _converted.activeStep.id : null;
                    const dispatchSteps =
                      execution?.steps.filter(step => step.action === 'dispatch_parallel_tasks') || [];
                    const dispatchStepIndex = activeDispatchStepId
                      ? dispatchSteps.findIndex(step => step.id === activeDispatchStepId)
                      : -1;
                    const activeDispatchBatchId = dispatchStepIndex >= 0 ? dispatchStepIndex + 1 : null;
                    const parallelSubAgents = activeDispatchBatchId
                      ? Object.fromEntries(
                          Object.entries(execution?.subAgents || {}).filter(
                            ([, agent]) =>
                              agent.batchId === activeDispatchBatchId ||
                              (agent.batchId === 0 && activeDispatchBatchId === 1),
                          ),
                        )
                      : undefined;
                    if (activeSub) {
                      activeStep = {
                        id: `subagent-${activeSub.agentId}`,
                        type: 'task',
                        title: activeSub.name,
                        status:
                          activeSub.status === 'done'
                            ? 'completed'
                            : activeSub.status === 'running'
                              ? 'running'
                              : 'error',
                      };
                      // The sub-agent detail view consumes the structured steps
                      // directly. Keeping the main dispatch output here would
                      // duplicate titles/results and flatten step boundaries.
                      outputs = [];
                      isRunning = activeSub.status === 'running';
                    }

                    return (
                      <ManusRightPanel
                        activeStep={activeStep}
                        outputs={outputs}
                        databaseType={selectedDb?.db_type}
                        databaseName={selectedDb?.db_name}
                        isRunning={isRunning}
                        onRerun={router.query.from_task ? undefined : () => {}}
                        onShare={!loading && !!conversationId ? handleShare : undefined}
                        onSchedule={
                          !loading && !!conversationId && !router.query.from_task
                            ? () => setScheduleOpen(true)
                            : undefined
                        }
                        terminalTitle={t('db_gpt_computer')}
                        artifacts={artifacts.filter(a => a.messageId === activeViewMsg?.id)}
                        inputFiles={rounds.find(r => r.viewMsg?.id === activeViewMsg?.id)?.humanMsg?.attachedFiles}
                        onArtifactClick={artifact => {
                          if (artifact.type === 'html') {
                            setPreviewArtifact(artifact as Artifact);
                            setRightPanelView('html-preview');
                          } else if (artifact.type === 'code' && artifact.stepId) {
                            setSelectedStepId(artifact.stepId);
                            setRightPanelView('execution');
                            if (activeViewMsg?.id && execution) {
                              setExecutionMap(prev => ({
                                ...prev,
                                [activeViewMsg.id!]: {
                                  ...prev[activeViewMsg.id!],
                                  activeStepId: artifact.stepId!,
                                },
                              }));
                            }
                          } else if (artifact.type === 'file') {
                            if (/\.(png|jpg|jpeg|gif|webp|svg|bmp)$/i.test(artifact.name)) {
                              setPreviewArtifact(artifact as Artifact);
                              setRightPanelView('image-preview');
                              setRightPanelCollapsed(false);
                            }
                          } else if (artifact.type === 'image') {
                            setPreviewArtifact(artifact as Artifact);
                            setRightPanelView('image-preview');
                            setRightPanelCollapsed(false);
                          }
                        }}
                        panelView={rightPanelView}
                        onPanelViewChange={handleUserPanelViewChange}
                        previewArtifact={previewArtifact}
                        skillName={createdSkillNames[activeViewMsg?.id || ''] || null}
                        summaryContent={
                          summaryPresentationResponseId === activeViewMsg?.id
                            ? streamingSummary
                            : activeViewMsg?.context || ''
                        }
                        isSummaryStreaming={summaryPresentationResponseId === activeViewMsg?.id && !_summaryComplete}
                        citations={activeViewMsg?.citations || []}
                        selectedCitationIndex={
                          activeViewMsg?.citations?.some(citation => citation.index === selectedCitationIndex)
                            ? selectedCitationIndex
                            : null
                        }
                        onCitationSelect={setSelectedCitationIndex}
                        subAgents={parallelSubAgents}
                        onSubAgentClick={agentId => {
                          if (!activeViewMsg?.id) return;
                          setActiveSubAgent({ messageId: activeViewMsg.id, agentId });
                          setRightPanelView('execution');
                        }}
                        subAgentContext={activeSub || null}
                        onExitSubAgentView={() => setActiveSubAgent(null)}
                      />
                    );
                  })()
                )}
              </div>
            </div>
          ) : (
            // Welcome Mode: Display Hero Section
            <div className='flex-1 flex flex-col items-center justify-center px-6 py-4 pb-20 overflow-y-auto'>
              <div className='w-full max-w-[860px] flex flex-col items-center animate-fade-in-up'>
                <h1 className='text-4xl md:text-5xl font-serif text-gray-900 dark:text-gray-100 mb-4 text-center flex items-center gap-4'>
                  <div className='w-12 h-12 rounded-xl bg-white dark:bg-[#1a1b1e] shadow-md flex items-center justify-center flex-shrink-0'>
                    <Image src='/LOGO_SMALL.png' alt='DB-GPT' width={32} height={32} className='object-contain' />
                  </div>
                  {t('home_title')}
                </h1>

                <p className='text-sm md:text-base text-gray-400 dark:text-gray-500 tracking-[0.2em] font-light mb-10'>
                  {t('home_subtitle')}
                </p>

                {/* Input Box Container - Premium Layered Style */}
                <div className='w-full relative'>
                  {/* Outer Frame - Floating Effect */}
                  <div
                    className='w-full relative transition-all duration-500 rounded-[28px] shadow-[0_16px_48px_rgba(0,0,0,0.12),0_6px_20px_rgba(0,0,0,0.08)] hover:shadow-[0_24px_64px_rgba(0,0,0,0.2),0_12px_32px_rgba(0,0,0,0.1)] dark:shadow-[0_16px_48px_rgba(0,0,0,0.4)] dark:hover:shadow-[0_24px_64px_rgba(0,0,0,0.5)]'
                    {...composerDragHandlers}
                  >
                    {composerDragOverlay}
                    {/* White Inner Box - Clean Glass Card */}
                    <div className='bg-white/95 backdrop-blur-md dark:bg-[#1e1f24]/95 rounded-[28px] border border-gray-100 dark:border-[#33353b] shadow-[inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] p-5 relative z-10'>
                      <AttachmentRail
                        drafts={sessionFiles.files}
                        legacyFiles={sessionFiles.legacyFile ? [sessionFiles.legacyFile] : []}
                        onRemove={sessionFiles.remove}
                        onRetry={() => sessionFiles.retryFailed()}
                        onPreview={openSessionFilePreview}
                        onLegacyPreview={openLegacyFilePreview}
                        onClearAll={clearComposerAttachments}
                        addControl={
                          <Upload {...uploadProps}>
                            <AttachmentRailAddButton />
                          </Upload>
                        }
                        preview={showInlineAttachmentPreview ? null : sessionFilePreview}
                        onClosePreview={closeSessionFilePreview}
                        className='mb-2'
                      />
                      {/* Database, Knowledge, Connector Tags */}
                      {(selectedDb || selectedKnowledge || selectedConnectors.length > 0) && (
                        <div className='flex flex-wrap gap-2 mb-2'>
                          {selectedDb && (
                            <Tag
                              closable
                              onClose={() => setSelectedDb(null)}
                              className='flex items-center gap-1 bg-blue-50 border-blue-200 text-blue-700 px-3 py-1 rounded-full'
                            >
                              {getDbIcon(selectedDb.type)}{' '}
                              <span className='font-medium ml-1'>{selectedDb.db_name}</span>
                            </Tag>
                          )}
                          {selectedKnowledge && (
                            <Tag
                              closable
                              onClose={() => setSelectedKnowledge(null)}
                              className='flex items-center gap-1 bg-orange-50 border-orange-200 text-orange-700 px-3 py-1 rounded-full'
                            >
                              <BookOutlined /> <span className='font-medium ml-1'>{selectedKnowledge.name}</span>
                            </Tag>
                          )}
                          {selectedConnectors.length > 0 && (
                            <>
                              {selectedConnectors.map(c => (
                                <Tag
                                  key={c.id}
                                  closable
                                  onClose={() => setSelectedConnectors(prev => prev.filter(s => s.id !== c.id))}
                                  className='flex items-center gap-1 bg-violet-50 border-violet-200 text-violet-700 px-3 py-1 rounded-full'
                                >
                                  <ApiOutlined /> <span className='font-medium ml-1'>{c.display_name}</span>
                                </Tag>
                              ))}
                            </>
                          )}
                        </div>
                      )}

                      <Input.TextArea
                        value={query}
                        onChange={e => {
                          const newValue = e.target.value;
                          setQuery(newValue);
                          if (newValue === '/' && !isSkillPanelOpen && !selectedSkill) {
                            setIsSkillPanelOpen(true);
                          }
                        }}
                        onPressEnter={e => {
                          if (!e.shiftKey) {
                            e.preventDefault();
                            handleStart();
                          }
                        }}
                        placeholder={
                          t('ask_data_question') ||
                          'Ask a question about your database, upload a CSV, or generate a report...'
                        }
                        autoSize={{ minRows: 3, maxRows: 8 }}
                        className='text-lg resize-none !border-none !shadow-none !bg-transparent px-2 py-2 mb-2'
                        style={{ backgroundColor: 'transparent' }}
                      />

                      {/* Input Toolbar */}
                      <div className='flex items-center justify-between px-1 mt-1'>
                        <div className='flex items-center gap-4'>
                          {/* Add Button with Dropdown Menu */}
                          <Dropdown
                            menu={{
                              items: [
                                {
                                  key: 'upload',
                                  label: (
                                    <Upload {...uploadProps}>
                                      <div className='w-full'>{t('add_from_local')}</div>
                                    </Upload>
                                  ),
                                  icon: <PaperClipOutlined />,
                                },
                                {
                                  key: 'skill',
                                  label: t('use_skill'),
                                  icon: <ThunderboltOutlined />,
                                  onClick: () => setIsSkillPanelOpen(true),
                                },
                                {
                                  key: 'knowledge',
                                  label: t('use_knowledge'),
                                  icon: <BookOutlined />,
                                  onClick: () => setIsKnowledgePanelOpen(true),
                                },
                                {
                                  key: 'database',
                                  label: t('use_database'),
                                  icon: <DatabaseOutlined />,
                                  onClick: () => setTimeout(() => setIsDbPanelOpen(true), 100),
                                },
                                {
                                  key: 'connector',
                                  label: t('use_connector'),
                                  icon: <ApiOutlined />,
                                  onClick: () => setIsConnectorPanelOpen(true),
                                },
                              ],
                            }}
                            trigger={['click']}
                          >
                            <Tooltip title={t('add_context')}>
                              <Button
                                type='text'
                                shape='circle'
                                size='small'
                                icon={<PlusOutlined />}
                                className='flex items-center justify-center text-gray-500 hover:text-violet-600 bg-gradient-to-b from-white to-gray-50 dark:from-[#2a2b2f] dark:to-[#1e1f24] dark:text-gray-300 border border-gray-200/80 dark:border-white/10 shadow-[0_1px_2px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.05)] hover:-translate-y-[0.5px] hover:shadow-[0_2px_4px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,1)] dark:hover:border-white/20 transition-all flex-shrink-0'
                              />
                            </Tooltip>
                          </Dropdown>

                          {/* Skill Selector Button with Badge - Purple Gradient */}
                          <Popover
                            trigger='click'
                            placement='topLeft'
                            open={isSkillPanelOpen}
                            onOpenChange={setIsSkillPanelOpen}
                            overlayClassName='manus-skill-menu'
                            overlayInnerStyle={{ padding: 0, borderRadius: 12 }}
                            content={
                              <div className='w-[320px] bg-white dark:bg-[#2c2d31] rounded-xl shadow-xl overflow-hidden'>
                                <div className='p-3 border-b border-gray-100 dark:border-gray-700'>
                                  <Input
                                    placeholder={t('search_skill')}
                                    prefix={<SearchOutlined className='text-gray-400' />}
                                    value={skillSearchQuery}
                                    onChange={e => setSkillSearchQuery(e.target.value)}
                                    className='rounded-lg'
                                    allowClear
                                    size='small'
                                  />
                                </div>
                                <div className='max-h-[300px] overflow-y-auto'>
                                  {(skillsList || [])
                                    .filter(
                                      skill =>
                                        !skillSearchQuery ||
                                        skill.name.toLowerCase().includes(skillSearchQuery.toLowerCase()) ||
                                        skill.description.toLowerCase().includes(skillSearchQuery.toLowerCase()),
                                    )
                                    .map(skill => (
                                      <div
                                        key={skill.id}
                                        onClick={() => {
                                          if (selectedSkill?.id === skill.id) {
                                            setSelectedSkill(null);
                                            setQuery('');
                                          } else {
                                            setSelectedSkill(skill);
                                            setQuery(`/${skill.name} `);
                                          }
                                          setIsSkillPanelOpen(false);
                                          setSkillSearchQuery('');
                                        }}
                                        className={`flex items-start gap-3 px-3 py-2.5 cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-800 ${
                                          selectedSkill?.id === skill.id ? 'bg-purple-50 dark:bg-purple-900/20' : ''
                                        }`}
                                      >
                                        <div className='flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-purple-500 to-blue-500 flex items-center justify-center text-white text-xs'>
                                          {skill.icon || <ThunderboltOutlined />}
                                        </div>
                                        <div className='flex-1 min-w-0'>
                                          <div className='flex items-center gap-2'>
                                            <span className='font-medium text-sm text-gray-800 dark:text-gray-200'>
                                              {skill.name}
                                            </span>
                                            <span
                                              className={`text-[10px] px-1.5 py-0.5 rounded ${
                                                skill.type === 'official'
                                                  ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
                                                  : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                                              }`}
                                            >
                                              {skill.type === 'official'
                                                ? t('picker_skill_official')
                                                : t('picker_skill_personal')}
                                            </span>
                                          </div>
                                          <p className='text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2'>
                                            {skill.description}
                                          </p>
                                        </div>
                                        {selectedSkill?.id === skill.id && (
                                          <CheckCircleFilled className='text-purple-500 flex-shrink-0 text-sm' />
                                        )}
                                      </div>
                                    ))}
                                  {(skillsList || []).filter(
                                    skill =>
                                      !skillSearchQuery ||
                                      skill.name.toLowerCase().includes(skillSearchQuery.toLowerCase()) ||
                                      skill.description.toLowerCase().includes(skillSearchQuery.toLowerCase()),
                                  ).length === 0 && (
                                    <div className='text-center py-8 text-gray-400'>
                                      <ThunderboltOutlined className='text-2xl mb-2 opacity-50' />
                                      <div className='text-xs'>
                                        {skillSearchQuery ? t('picker_skill_no_match') : t('picker_skill_empty')}
                                      </div>
                                    </div>
                                  )}
                                </div>
                                <div className='border-t border-gray-100 dark:border-gray-700 px-3 py-2 flex items-center justify-between bg-gray-50/50 dark:bg-gray-900/50'>
                                  <span className='text-[10px] text-gray-400'>
                                    {t('picker_skill_count', { count: (skillsList || []).length })}
                                  </span>
                                  <Button
                                    type='link'
                                    size='small'
                                    onClick={() => {
                                      router.push('/construct/skills');
                                      setIsSkillPanelOpen(false);
                                    }}
                                    className='text-[10px] p-0 h-auto'
                                  >
                                    {t('picker_manage_skill')}
                                  </Button>
                                </div>
                              </div>
                            }
                          >
                            <Tooltip
                              title={
                                selectedSkill ? t('skill_selected', { name: selectedSkill.name }) : t('select_skill')
                              }
                            >
                              <Button
                                type='text'
                                shape='circle'
                                size='small'
                                className={`relative flex items-center justify-center flex-shrink-0 transition-all ${
                                  selectedSkill
                                    ? 'bg-gradient-to-br from-[#a78bfa] to-[#7c3aed] text-white border border-transparent shadow-[0_2px_4px_rgba(139,92,246,0.3),inset_0_1px_0_rgba(255,255,255,0.3)] hover:-translate-y-[0.5px] hover:shadow-[0_4px_8px_rgba(139,92,246,0.4),inset_0_1px_0_rgba(255,255,255,0.3)]'
                                    : 'text-gray-500 hover:text-violet-600 bg-gradient-to-b from-white to-gray-50 dark:from-[#2a2b2f] dark:to-[#1e1f24] dark:text-gray-300 border border-gray-200/80 dark:border-white/10 shadow-[0_1px_2px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.05)] hover:-translate-y-[0.5px] hover:shadow-[0_2px_4px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,1)] dark:hover:border-white/20'
                                }`}
                              >
                                <div className='relative'>
                                  <ThunderboltOutlined className={selectedSkill ? 'text-white' : ''} />
                                  {selectedSkill && (
                                    <span className='absolute -top-1.5 -right-1.5 bg-white text-[#7c3aed] text-[8px] rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold shadow-sm ring-1 ring-[#7c3aed]/30'>
                                      1
                                    </span>
                                  )}
                                </div>
                              </Button>
                            </Tooltip>
                          </Popover>

                          {/* Connector Selector Button */}
                          <Popover
                            trigger='click'
                            placement='topLeft'
                            open={isConnectorPanelOpen}
                            onOpenChange={setIsConnectorPanelOpen}
                            overlayClassName='manus-skill-menu'
                            overlayInnerStyle={{ padding: 0, borderRadius: 12 }}
                            content={
                              <div className='w-[320px] bg-white dark:bg-[#2c2d31] rounded-xl shadow-xl overflow-hidden'>
                                <div className='p-3 border-b border-gray-100 dark:border-gray-700'>
                                  <Input
                                    placeholder={t('search_connector')}
                                    prefix={<SearchOutlined className='text-gray-400' />}
                                    value={connectorSearchQuery}
                                    onChange={e => setConnectorSearchQuery(e.target.value)}
                                    className='rounded-lg'
                                    allowClear
                                    size='small'
                                  />
                                </div>
                                <div className='max-h-[300px] overflow-y-auto'>
                                  {(connectorsList || [])
                                    .filter(
                                      (c: ConnectorInstance) =>
                                        c.status === 'active' &&
                                        (!connectorSearchQuery ||
                                          c.display_name.toLowerCase().includes(connectorSearchQuery.toLowerCase()) ||
                                          c.connector_type.toLowerCase().includes(connectorSearchQuery.toLowerCase())),
                                    )
                                    .map((c: ConnectorInstance) => (
                                      <div
                                        key={c.id}
                                        onClick={() => {
                                          setSelectedConnectors(prev =>
                                            prev.some(s => s.id === c.id)
                                              ? prev.filter(s => s.id !== c.id)
                                              : [...prev, c],
                                          );
                                          setConnectorSearchQuery('');
                                        }}
                                        className={`flex items-start gap-3 px-3 py-2.5 cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-800 ${
                                          selectedConnectors.some(s => s.id === c.id)
                                            ? 'bg-violet-50 dark:bg-violet-900/20'
                                            : ''
                                        }`}
                                      >
                                        <div className='flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-500 flex items-center justify-center text-white text-xs'>
                                          <ApiOutlined />
                                        </div>
                                        <div className='flex-1 min-w-0'>
                                          <div className='flex items-center gap-2'>
                                            <span className='font-medium text-sm text-gray-800 dark:text-gray-200'>
                                              {c.display_name}
                                            </span>
                                            <span className='text-[10px] px-1.5 py-0.5 rounded bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'>
                                              {t('picker_connector_active')}
                                            </span>
                                          </div>
                                          <p
                                            className='text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate'
                                            title={(c.config?.description as string) || c.connector_type}
                                          >
                                            {(c.config?.description as string) || c.connector_type}
                                          </p>
                                        </div>
                                        {selectedConnectors.some(s => s.id === c.id) && (
                                          <CheckCircleFilled className='text-violet-500 flex-shrink-0 text-sm' />
                                        )}
                                      </div>
                                    ))}
                                  {(connectorsList || []).filter(
                                    (c: ConnectorInstance) =>
                                      c.status === 'active' &&
                                      (!connectorSearchQuery ||
                                        c.display_name.toLowerCase().includes(connectorSearchQuery.toLowerCase()) ||
                                        c.connector_type.toLowerCase().includes(connectorSearchQuery.toLowerCase())),
                                  ).length === 0 && (
                                    <div className='text-center py-8 text-gray-400'>
                                      <ApiOutlined className='text-2xl mb-2 opacity-50' />
                                      <div className='text-xs'>
                                        {connectorSearchQuery
                                          ? t('picker_connector_no_match')
                                          : t('picker_connector_empty')}
                                      </div>
                                    </div>
                                  )}
                                </div>
                                <div className='border-t border-gray-100 dark:border-gray-700 px-3 py-2 flex items-center justify-between bg-gray-50/50 dark:bg-gray-900/50'>
                                  <span className='text-[10px] text-gray-400'>
                                    {t('picker_connector_count', {
                                      count: (connectorsList || []).filter(
                                        (c: ConnectorInstance) => c.status === 'active',
                                      ).length,
                                    })}
                                  </span>
                                  <Button
                                    type='link'
                                    size='small'
                                    onClick={() => {
                                      router.push('/construct/connectors');
                                      setIsConnectorPanelOpen(false);
                                    }}
                                    className='text-[10px] p-0 h-auto'
                                  >
                                    {t('picker_manage_connector')}
                                  </Button>
                                </div>
                              </div>
                            }
                          >
                            <Tooltip
                              title={
                                selectedConnectors.length === 0
                                  ? t('select_mcp')
                                  : selectedConnectors.length === 1
                                    ? t('connector_selected', { name: selectedConnectors[0].display_name })
                                    : t('connectors_selected', {
                                        count: selectedConnectors.length,
                                        names: selectedConnectors.map(c => c.display_name).join('、'),
                                      })
                              }
                            >
                              <Button
                                type='text'
                                shape='circle'
                                size='small'
                                className={`relative flex items-center justify-center flex-shrink-0 transition-all ${
                                  selectedConnectors.length > 0
                                    ? 'bg-gradient-to-br from-[#8b5cf6] to-[#6366f1] text-white border border-transparent shadow-[0_2px_4px_rgba(139,92,246,0.3),inset_0_1px_0_rgba(255,255,255,0.3)] hover:-translate-y-[0.5px] hover:shadow-[0_4px_8px_rgba(139,92,246,0.4),inset_0_1px_0_rgba(255,255,255,0.3)]'
                                    : 'text-gray-500 hover:text-violet-600 bg-gradient-to-b from-white to-gray-50 dark:from-[#2a2b2f] dark:to-[#1e1f24] dark:text-gray-300 border border-gray-200/80 dark:border-white/10 shadow-[0_1px_2px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.05)] hover:-translate-y-[0.5px] hover:shadow-[0_2px_4px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,1)] dark:hover:border-white/20'
                                }`}
                              >
                                <div className='relative'>
                                  <ApiOutlined className={selectedConnectors.length > 0 ? 'text-white' : ''} />
                                  {selectedConnectors.length > 0 && (
                                    <span className='absolute -top-1.5 -right-1.5 bg-white text-violet-600 text-[8px] rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold shadow-sm ring-1 ring-violet-500/30'>
                                      {selectedConnectors.length}
                                    </span>
                                  )}
                                </div>
                              </Button>
                            </Tooltip>
                          </Popover>

                          {/* Database Selector Popover - Blue themed */}
                          <Popover
                            trigger='click'
                            placement='topLeft'
                            open={isDbPanelOpen}
                            onOpenChange={setIsDbPanelOpen}
                            overlayClassName='manus-database-menu'
                            overlayInnerStyle={{ padding: 0, borderRadius: 12 }}
                            content={
                              <div className='w-[320px] bg-white dark:bg-[#2c2d31] rounded-xl shadow-xl overflow-hidden'>
                                <div className='p-3 border-b border-gray-100 dark:border-gray-700'>
                                  <Input
                                    placeholder={t('search_database')}
                                    prefix={<SearchOutlined className='text-gray-400' />}
                                    value={dbSearchQuery}
                                    onChange={e => setDbSearchQuery(e.target.value)}
                                    className='rounded-lg'
                                    allowClear
                                    size='small'
                                  />
                                </div>
                                <div className='max-h-[300px] overflow-y-auto'>
                                  {(dataSources || [])
                                    .filter(
                                      ds =>
                                        !dbSearchQuery ||
                                        ds.db_name.toLowerCase().includes(dbSearchQuery.toLowerCase()) ||
                                        ds.type.toLowerCase().includes(dbSearchQuery.toLowerCase()) ||
                                        (ds.description &&
                                          ds.description.toLowerCase().includes(dbSearchQuery.toLowerCase())),
                                    )
                                    .map(ds => (
                                      <div
                                        key={ds.id}
                                        onClick={() => {
                                          setSelectedDb(ds);
                                          setIsDbPanelOpen(false);
                                          setDbSearchQuery('');
                                        }}
                                        className={`flex items-start gap-3 px-3 py-2.5 cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-800 ${
                                          selectedDb?.id === ds.id ? 'bg-blue-50 dark:bg-blue-900/20' : ''
                                        }`}
                                      >
                                        <div className='flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center text-white text-xs'>
                                          {getDbIcon(ds.type)}
                                        </div>
                                        <div className='flex-1 min-w-0'>
                                          <div className='flex items-center gap-2'>
                                            <span className='font-medium text-sm text-gray-800 dark:text-gray-200'>
                                              {ds.db_name}
                                            </span>
                                            <span className='text-[10px] text-gray-400 bg-gray-100 dark:bg-gray-700 rounded px-1.5 py-0.5'>
                                              {ds.type}
                                            </span>
                                          </div>
                                          {ds.description && (
                                            <p className='text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2'>
                                              {ds.description}
                                            </p>
                                          )}
                                        </div>
                                        {selectedDb?.id === ds.id && (
                                          <CheckCircleFilled className='text-blue-500 flex-shrink-0 text-sm' />
                                        )}
                                      </div>
                                    ))}
                                  {(dataSources || []).filter(
                                    ds =>
                                      !dbSearchQuery ||
                                      ds.db_name.toLowerCase().includes(dbSearchQuery.toLowerCase()) ||
                                      ds.type.toLowerCase().includes(dbSearchQuery.toLowerCase()) ||
                                      (ds.description &&
                                        ds.description.toLowerCase().includes(dbSearchQuery.toLowerCase())),
                                  ).length === 0 && (
                                    <div className='text-center py-8 text-gray-400'>
                                      <DatabaseOutlined className='text-2xl mb-2 opacity-50' />
                                      <div className='text-xs'>
                                        {dbSearchQuery ? t('picker_database_no_match') : t('picker_database_empty')}
                                      </div>
                                    </div>
                                  )}
                                </div>
                                <div className='border-t border-gray-100 dark:border-gray-700 px-3 py-2 flex items-center justify-between bg-gray-50/50 dark:bg-gray-900/50'>
                                  <span className='text-[10px] text-gray-400'>
                                    {t('picker_database_count', { count: (dataSources || []).length })}
                                  </span>
                                  <Button
                                    type='link'
                                    size='small'
                                    onClick={() => {
                                      router.push('/construct/database');
                                      setIsDbPanelOpen(false);
                                    }}
                                    className='text-[10px] p-0 h-auto'
                                  >
                                    {t('picker_manage_database')}
                                  </Button>
                                </div>
                              </div>
                            }
                          >
                            <Tooltip
                              title={
                                selectedDb ? t('database_selected', { name: selectedDb.db_name }) : t('select_database')
                              }
                            >
                              <Button
                                type='text'
                                shape='circle'
                                size='small'
                                className={`relative flex items-center justify-center flex-shrink-0 transition-all ${
                                  selectedDb
                                    ? 'bg-gradient-to-br from-blue-400 to-blue-600 text-white border border-transparent shadow-[0_2px_4px_rgba(59,130,246,0.3),inset_0_1px_0_rgba(255,255,255,0.3)] hover:-translate-y-[0.5px] hover:shadow-[0_4px_8px_rgba(59,130,246,0.4),inset_0_1px_0_rgba(255,255,255,0.3)]'
                                    : 'text-gray-500 hover:text-blue-600 bg-gradient-to-b from-white to-gray-50 dark:from-[#2a2b2f] dark:to-[#1e1f24] dark:text-gray-300 border border-gray-200/80 dark:border-white/10 shadow-[0_1px_2px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.05)] hover:-translate-y-[0.5px] hover:shadow-[0_2px_4px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,1)] dark:hover:border-white/20'
                                }`}
                              >
                                <div className='relative'>
                                  <DatabaseOutlined className={selectedDb ? 'text-white' : ''} />
                                  {selectedDb && (
                                    <span className='absolute -top-1.5 -right-1.5 bg-white text-blue-600 text-[8px] rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold shadow-sm ring-1 ring-blue-400/30'>
                                      1
                                    </span>
                                  )}
                                </div>
                              </Button>
                            </Tooltip>
                          </Popover>

                          {/* Knowledge Base Selector - Orange themed */}
                          <Popover
                            trigger='click'
                            placement='topLeft'
                            open={isKnowledgePanelOpen}
                            onOpenChange={setIsKnowledgePanelOpen}
                            overlayClassName='manus-knowledge-menu'
                            overlayInnerStyle={{ padding: 0, borderRadius: 12 }}
                            content={
                              <div className='w-[320px] bg-white dark:bg-[#2c2d31] rounded-xl shadow-xl overflow-hidden'>
                                <div className='p-3 border-b border-gray-100 dark:border-gray-700'>
                                  <Input
                                    placeholder={t('search_knowledge')}
                                    prefix={<SearchOutlined className='text-gray-400' />}
                                    value={knowledgeSearchQuery}
                                    onChange={e => setKnowledgeSearchQuery(e.target.value)}
                                    className='rounded-lg'
                                    allowClear
                                    size='small'
                                  />
                                </div>
                                <div className='max-h-[300px] overflow-y-auto'>
                                  {(knowledgeSpaces || [])
                                    .filter(
                                      space =>
                                        !knowledgeSearchQuery ||
                                        space.name.toLowerCase().includes(knowledgeSearchQuery.toLowerCase()) ||
                                        (space.desc &&
                                          space.desc.toLowerCase().includes(knowledgeSearchQuery.toLowerCase())),
                                    )
                                    .map(space => (
                                      <div
                                        key={space.id}
                                        onClick={() => {
                                          setSelectedKnowledge(space);
                                          setIsKnowledgePanelOpen(false);
                                          setKnowledgeSearchQuery('');
                                        }}
                                        className={`flex items-start gap-3 px-3 py-2.5 cursor-pointer transition-all hover:bg-gray-50 dark:hover:bg-gray-800 ${
                                          selectedKnowledge?.id === space.id ? 'bg-orange-50 dark:bg-orange-900/20' : ''
                                        }`}
                                      >
                                        <div className='flex-shrink-0 w-7 h-7 rounded-lg bg-gradient-to-br from-orange-500 to-red-500 flex items-center justify-center text-white text-xs'>
                                          <BookOutlined />
                                        </div>
                                        <div className='flex-1 min-w-0'>
                                          <div className='flex items-center gap-2'>
                                            <span className='font-medium text-sm text-gray-800 dark:text-gray-200'>
                                              {space.name}
                                            </span>
                                          </div>
                                          {space.desc && (
                                            <p className='text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2'>
                                              {space.desc}
                                            </p>
                                          )}
                                        </div>
                                        {selectedKnowledge?.id === space.id && (
                                          <CheckCircleFilled className='text-orange-500 flex-shrink-0 text-sm' />
                                        )}
                                      </div>
                                    ))}
                                  {(knowledgeSpaces || []).filter(
                                    space =>
                                      !knowledgeSearchQuery ||
                                      space.name.toLowerCase().includes(knowledgeSearchQuery.toLowerCase()) ||
                                      (space.desc &&
                                        space.desc.toLowerCase().includes(knowledgeSearchQuery.toLowerCase())),
                                  ).length === 0 && (
                                    <div className='text-center py-8 text-gray-400'>
                                      <BookOutlined className='text-2xl mb-2 opacity-50' />
                                      <div className='text-xs'>
                                        {knowledgeSearchQuery
                                          ? t('picker_knowledge_no_match')
                                          : t('picker_knowledge_empty')}
                                      </div>
                                    </div>
                                  )}
                                </div>
                                <div className='border-t border-gray-100 dark:border-gray-700 px-3 py-2 flex items-center justify-between bg-gray-50/50 dark:bg-gray-900/50'>
                                  <span className='text-[10px] text-gray-400'>
                                    {t('picker_knowledge_count', { count: (knowledgeSpaces || []).length })}
                                  </span>
                                  <Button
                                    type='link'
                                    size='small'
                                    onClick={() => {
                                      router.push('/construct/knowledge');
                                      setIsKnowledgePanelOpen(false);
                                    }}
                                    className='text-[10px] p-0 h-auto'
                                  >
                                    {t('picker_manage_knowledge')}
                                  </Button>
                                </div>
                              </div>
                            }
                          >
                            <Tooltip
                              title={
                                selectedKnowledge
                                  ? t('knowledge_selected', { name: selectedKnowledge.name })
                                  : t('select_knowledge')
                              }
                            >
                              <Button
                                type='text'
                                shape='circle'
                                size='small'
                                className={`relative flex items-center justify-center flex-shrink-0 transition-all ${
                                  selectedKnowledge
                                    ? 'bg-gradient-to-br from-orange-400 to-orange-600 text-white border border-transparent shadow-[0_2px_4px_rgba(249,115,22,0.3),inset_0_1px_0_rgba(255,255,255,0.3)] hover:-translate-y-[0.5px] hover:shadow-[0_4px_8px_rgba(249,115,22,0.4),inset_0_1px_0_rgba(255,255,255,0.3)]'
                                    : 'text-gray-500 hover:text-orange-600 bg-gradient-to-b from-white to-gray-50 dark:from-[#2a2b2f] dark:to-[#1e1f24] dark:text-gray-300 border border-gray-200/80 dark:border-white/10 shadow-[0_1px_2px_rgba(0,0,0,0.05),inset_0_1px_0_rgba(255,255,255,1)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.2),inset_0_1px_0_rgba(255,255,255,0.05)] hover:-translate-y-[0.5px] hover:shadow-[0_2px_4px_rgba(0,0,0,0.06),inset_0_1px_0_rgba(255,255,255,1)] dark:hover:border-white/20'
                                }`}
                              >
                                <div className='relative'>
                                  <BookOutlined className={selectedKnowledge ? 'text-white' : ''} />
                                  {selectedKnowledge && (
                                    <span className='absolute -top-1.5 -right-1.5 bg-white text-orange-600 text-[8px] rounded-full w-3.5 h-3.5 flex items-center justify-center font-bold shadow-sm ring-1 ring-orange-400/30'>
                                      1
                                    </span>
                                  )}
                                </div>
                              </Button>
                            </Tooltip>
                          </Popover>

                          {/* Separator */}
                          <div className='w-px h-4 bg-gray-200 dark:bg-gray-700 mx-0.5' />

                          {/* Model Selector with premium styling */}
                          <div className='model-selector-premium'>
                            <ModelSelector onChange={val => setModel(val)} />
                          </div>
                          <style
                            dangerouslySetInnerHTML={{
                              __html: `
                                  .model-selector-premium .ant-select { border-radius: 8px !important; border: none !important; }
                                  .model-selector-premium .ant-select-selector { background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%) !important; border: 1px solid rgba(0,0,0,0.12) !important; box-shadow: 0 1px 2px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,1) !important; border-radius: 8px !important; transition: all 0.2s ease !important; padding: 0 8px !important; }
                                  .dark .model-selector-premium .ant-select-selector { background: linear-gradient(180deg, #2a2b2f 0%, #1e1f24 100%) !important; border: 1px solid rgba(255,255,255,0.1) !important; box-shadow: 0 1px 2px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.05) !important; }
                                  .model-selector-premium .ant-select:hover .ant-select-selector { border-color: rgba(0,0,0,0.2) !important; box-shadow: 0 2px 4px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,1) !important; transform: translateY(-0.5px); }
                                  .dark .model-selector-premium .ant-select:hover .ant-select-selector { border-color: rgba(255,255,255,0.15) !important; }
                                  .model-selector-premium .ant-select-focused .ant-select-selector { border-color: #a78bfa !important; box-shadow: 0 0 0 2px rgba(167,139,250,0.15), inset 0 1px 0 rgba(255,255,255,1) !important; }
                                  .dark .model-selector-premium .ant-select-focused .ant-select-selector { box-shadow: 0 0 0 2px rgba(167,139,250,0.2), inset 0 1px 0 rgba(255,255,255,0.05) !important; }
                                  
                                  /* Global Dropdown Item Styles for Model Selectors */
                                  .ant-select-dropdown .ant-select-item-option-selected { background-color: #f1f5f9 !important; color: #0f172a !important; font-weight: 500 !important; }
                                  .ant-select-dropdown .ant-select-item-option-active:not(.ant-select-item-option-selected) { background-color: #f8fafc !important; }
                                  .dark .ant-select-dropdown .ant-select-item-option-selected { background-color: rgba(255,255,255,0.08) !important; color: #e2e8f0 !important; }
                                  .dark .ant-select-dropdown .ant-select-item-option-active:not(.ant-select-item-option-selected) { background-color: rgba(255,255,255,0.04) !important; }
                                `,
                            }}
                          />
                        </div>

                        <div className='flex items-center gap-3'>
                          {/* Voice Button */}
                          <Tooltip title={t('voice_input')}>
                            <Button
                              type='text'
                              shape='circle'
                              size='large'
                              icon={<AudioOutlined className='text-gray-500 text-xl' />}
                              onClick={() => message.info(t('voice_input_coming_soon'))}
                              className='flex-shrink-0 transition-all duration-200 flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-800'
                            />
                          </Tooltip>

                          {/* Send Button with blue gradient + gloss */}
                          <Button
                            type='primary'
                            shape={queuedSendAfterUpload ? 'round' : 'circle'}
                            size='large'
                            icon={queuedSendAfterUpload ? undefined : <ArrowUpOutlined />}
                            onClick={() => handleStart()}
                            disabled={
                              (!query.trim() && !hasSessionFileDrafts && !hasLegacyFile) ||
                              loading ||
                              queuedSendAfterUpload
                            }
                            loading={loading || queuedSendAfterUpload}
                            className={`group/send relative overflow-hidden border-none shadow-lg transition-all duration-200 ${
                              queuedSendAfterUpload ? 'px-4' : ''
                            } ${
                              query.trim() || hasSessionFileDrafts || hasLegacyFile
                                ? 'bg-gradient-to-br from-[#3b82f6] to-[#2563eb] hover:shadow-blue-300/40 hover:shadow-xl hover:scale-105'
                                : 'bg-gray-200 text-gray-400'
                            }`}
                            style={
                              query.trim() || hasSessionFileDrafts || hasLegacyFile
                                ? { background: 'linear-gradient(135deg, #3b82f6, #2563eb)' }
                                : undefined
                            }
                          >
                            {queuedSendAfterUpload && <span className='text-[13px] font-medium'>上传后发送</span>}
                            {(query.trim() || hasSessionFileDrafts || hasLegacyFile) && (
                              <span
                                className='absolute inset-0 opacity-0 group-hover/send:opacity-100 transition-opacity duration-300 pointer-events-none'
                                style={{
                                  background:
                                    'linear-gradient(105deg, transparent 40%, rgba(255,255,255,0.25) 45%, rgba(255,255,255,0.35) 50%, rgba(255,255,255,0.25) 55%, transparent 60%)',
                                  animation: 'glossSweepHero 1.8s ease-in-out infinite',
                                }}
                              />
                            )}
                          </Button>
                        </div>
                        <style
                          dangerouslySetInnerHTML={{
                            __html: `@keyframes glossSweepHero { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }`,
                          }}
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Recommended Examples */}
                <div className='mt-10 w-full'>
                  <div className='flex items-center justify-center gap-2 mb-4'>
                    <div className='h-px flex-1 bg-gradient-to-r from-transparent to-gray-200 dark:to-gray-700' />
                    <span className='text-xs font-medium text-gray-400 dark:text-gray-500 tracking-wider uppercase'>
                      {t('recommend_examples')}
                    </span>
                    <div className='h-px flex-1 bg-gradient-to-l from-transparent to-gray-200 dark:to-gray-700' />
                  </div>
                  <div className='grid grid-cols-1 sm:grid-cols-2 gap-3'>
                    {EXAMPLE_CARDS.map(example => (
                      <div
                        key={example.id}
                        onClick={() => handleExampleClick(example)}
                        className={`group relative bg-gradient-to-br ${example.color} border ${example.borderColor} rounded-2xl p-4 cursor-pointer hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300`}
                      >
                        <div className='flex items-start gap-3'>
                          <div
                            className={`w-10 h-10 ${example.iconBg} rounded-xl flex items-center justify-center text-xl flex-shrink-0`}
                          >
                            {example.icon}
                          </div>
                          <div className='flex-1 min-w-0'>
                            <h3 className='text-sm font-semibold text-gray-800 dark:text-gray-200 mb-1'>
                              {(() => {
                                const key = `example_${example.id}_title`;
                                const val = t(key) as string;
                                return val && val !== key ? val : example.title;
                              })()}
                            </h3>
                            <p className='text-xs text-gray-500 dark:text-gray-400 line-clamp-2'>
                              {(() => {
                                const key = `example_${example.id}_desc`;
                                const val = t(key) as string;
                                return val && val !== key ? val : example.description;
                              })()}
                            </p>
                          </div>
                        </div>
                        <div className='absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity'>
                          <RightOutlined className='text-xs text-gray-400' />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Footer Promo - Only show when no messages */}
          {messages.length === 0 && (
            <div className='absolute bottom-6 left-0 right-0 flex justify-center'>
              <div className='bg-white/60 dark:bg-[#1e1f24]/60 backdrop-blur-sm px-5 py-2.5 rounded-full border border-gray-100 dark:border-gray-700/50 flex items-center gap-3 shadow-sm cursor-pointer hover:shadow-md hover:bg-white/90 dark:hover:bg-[#1e1f24]/90 transition-all duration-300'>
                <Image src='/LOGO_SMALL.png' alt='DB-GPT' width={22} height={22} className='object-contain' />
                <span className='text-xs font-medium text-gray-600 dark:text-gray-300 tracking-wide'>
                  {t('home_subtitle')}
                </span>
                <span className='text-[10px] text-gray-400 dark:text-gray-500'>·</span>
                <span className='text-[10px] text-gray-400 dark:text-gray-500'>{t('home_title')}</span>
              </div>
            </div>
          )}
        </div>

        {/* Database Selection Modal */}
        <Modal
          title={
            <div className='flex items-center gap-2'>
              <DatabaseOutlined />
              Select Data Source
            </div>
          }
          open={isDbModalOpen}
          onCancel={() => setIsDbModalOpen(false)}
          footer={null}
          width={500}
        >
          <List
            itemLayout='horizontal'
            dataSource={dataSources || []}
            renderItem={(item: DataSource) => (
              <List.Item
                className={`cursor-pointer hover:bg-gray-50 rounded-lg px-2 transition-colors ${selectedDb?.id === item.id ? 'bg-blue-50' : ''}`}
                onClick={() => {
                  setSelectedDb(item);
                  setIsDbModalOpen(false);
                }}
                actions={[selectedDb?.id === item.id && <CheckCircleFilled className='text-blue-500' />]}
              >
                <List.Item.Meta
                  avatar={<div className='mt-1 bg-gray-100 p-2 rounded-lg'>{getDbIcon(item.type)}</div>}
                  title={item.db_name}
                  description={<span className='text-xs text-gray-400'>{item.type}</span>}
                />
              </List.Item>
            )}
            locale={{ emptyText: 'No data sources found' }}
          />
          <div className='mt-4 pt-4 border-t border-gray-100 text-center'>
            <Button type='dashed' block icon={<PlusOutlined />} onClick={() => router.push('/construct/database')}>
              Add New Data Source
            </Button>
          </div>
        </Modal>

        {/* Knowledge Base Selection Modal */}
        <Modal
          title={
            <div className='flex items-center gap-2'>
              <BookOutlined />
              Select Knowledge Base
            </div>
          }
          open={isKnowledgeModalOpen}
          onCancel={() => setIsKnowledgeModalOpen(false)}
          footer={null}
          width={500}
        >
          <List
            itemLayout='horizontal'
            dataSource={knowledgeSpaces || []}
            renderItem={(item: KnowledgeSpace) => (
              <List.Item
                className={`cursor-pointer hover:bg-gray-50 rounded-lg px-2 transition-colors ${selectedKnowledge?.id === item.id ? 'bg-orange-50' : ''}`}
                onClick={() => {
                  setSelectedKnowledge(item);
                  setIsKnowledgeModalOpen(false);
                }}
                actions={[selectedKnowledge?.id === item.id && <CheckCircleFilled className='text-orange-500' />]}
              >
                <List.Item.Meta
                  avatar={
                    <div className='mt-1 bg-gray-100 p-2 rounded-lg'>
                      <ReadOutlined className='text-orange-500' />
                    </div>
                  }
                  title={item.name}
                  description={<span className='text-xs text-gray-400'>{item.vector_type}</span>}
                />
              </List.Item>
            )}
            locale={{ emptyText: 'No knowledge bases found' }}
          />
          <div className='mt-4 pt-4 border-t border-gray-100 text-center'>
            <Button type='dashed' block icon={<PlusOutlined />} onClick={() => router.push('/construct/knowledge')}>
              Add New Knowledge Base
            </Button>
          </div>
        </Modal>
        <SaveAsScheduledTaskDrawer
          open={isScheduleOpen}
          onClose={() => setScheduleOpen(false)}
          snapshot={buildSnapshot()}
        />
        {/* Hero view has no right panel; desktop previews there fall back to a Drawer. */}
        {sessionFilePreview && isDesktopWidth && messages.length === 0 && (
          <Drawer
            open
            placement='right'
            destroyOnClose
            closable={false}
            width={PREVIEW_DRAWER_MAX_WIDTH}
            title={<AttachmentPreviewPanelTitle />}
            extra={<AttachmentPreviewCloseButton onClose={closeSessionFilePreview} />}
            styles={ATTACHMENT_PREVIEW_DRAWER_STYLES}
            onClose={closeSessionFilePreview}
          >
            {renderSessionFilePreviewBody()}
          </Drawer>
        )}
        <ConfirmDialog confirmation={pendingConfirmation} onApprove={approve} onDeny={deny} onDismiss={dismiss} />
      </div>
    </ConfigProvider>
  );
};

export default Playground;
