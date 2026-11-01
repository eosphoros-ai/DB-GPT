import { ensureDashboardAssistantTask, getDbList } from '@/client/api';
import { SELECTED_MODEL_STORAGE_KEY, isModelConnectionFailure } from '@/lib/model-runtime';
import type { DashboardRecord } from '@/types/dashboard';
import { getUserId } from '@/utils';
import { cleanAgentAnswer } from '@/utils/clean-agent-answer';
import { decodeFinalEvent } from '@/utils/react-agent-final';

/** Read complete SSE frames, including CRLF and an unterminated final frame. */
export async function readDashboardAssistantStream(
  body: ReadableStream<Uint8Array>,
  onStatus: (status: string) => void,
  onEvent?: (event: unknown) => void,
): Promise<string> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '',
    answer = '',
    failure = '';
  const process = (frame: string) => {
    const data = frame
      .split(/\r?\n/)
      .filter(line => line.startsWith('data:'))
      .map(line => line.slice(5).trim())
      .join('\n');
    if (!data || data === '[DONE]') return;
    let event: Record<string, unknown>;
    try {
      event = JSON.parse(data);
    } catch {
      return;
    }
    onEvent?.(event);
    if (event.type === 'final') answer = cleanAgentAnswer(decodeFinalEvent(event).content);
    if (event.type === 'error') failure = String(event.message || event.error || 'AI 请求失败，请重试');
    if (event.type === 'step.meta' && typeof event.action_intention === 'string') onStatus(event.action_intention);
    if (event.type === 'dashboard.proposal') onStatus('正在验证修改方案…');
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || '';
      frames.forEach(process);
      if (done) {
        if (buffer.trim()) process(buffer);
        break;
      }
    }
  } finally {
    reader.releaseLock();
  }
  if (failure || isModelConnectionFailure(answer)) throw new Error(failure || answer);
  if (!answer.trim()) throw new Error('连接已结束，但 AI 没有返回完整答复。批注已保留，可以重试。');
  return answer;
}
export async function runDashboardAssistant(
  record: DashboardRecord,
  prompt: string,
  onStatus: (status: string) => void,
  signal: AbortSignal,
  onEvent?: (event: unknown, conversationId?: string) => void,
) {
  const task = await ensureDashboardAssistantTask(record.id);
  if (!task.data.success || !task.data.data?.conversation_id) throw new Error(task.data.err_msg || '无法建立看板对话');
  const sources = await getDbList();
  if (!sources.data.success) throw new Error(sources.data.err_msg || '无法读取数据源');
  const source = (
    sources.data.data as unknown as Array<{
      db_name?: string;
      params?: { name?: string };
      type?: string;
      db_type?: string;
    }>
  ).find(item => (item.db_name || item.params?.name) === record.schema.dashboard.data_source_id);
  if (!source) throw new Error('看板数据源暂不可用，请恢复连接后重试');
  signal.throwIfAborted();
  const response = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/chat/react-agent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(getUserId() ? { 'User-Id': getUserId()! } : {}) },
    signal,
    body: JSON.stringify({
      conv_uid: task.data.data.conversation_id,
      chat_mode: 'chat_react_agent',
      select_param: '',
      model_name: localStorage.getItem(SELECTED_MODEL_STORAGE_KEY) || undefined,
      temperature: 0.3,
      max_new_tokens: 4000,
      user_input:
        prompt +
        '\n请在当前看板侧边对话中用中文答复。需要用户补充时，在最终答复中直接提出具体问题。不要创建新看板、不要直接应用修改。',
      ext_info: {
        creation_mode: 'dashboard',
        database_name: record.schema.dashboard.data_source_id,
        database_type: source.db_type || source.type,
      },
    }),
  });
  if (!response.ok) throw new Error(`AI 请求失败（${response.status}），批注已保留，请重试。`);
  if (!response.body) throw new Error('AI 未返回内容，请重试。');
  return readDashboardAssistantStream(response.body, onStatus, event =>
    onEvent?.(event, task.data.data.conversation_id),
  );
}
