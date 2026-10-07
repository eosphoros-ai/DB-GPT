export const SELECTED_MODEL_STORAGE_KEY = 'dbgpt-selected-model';

export const resolvePreferredModel = (currentModel: string, persistedModel: string | null, availableModels: string[]) =>
  currentModel || persistedModel || availableModels[0] || '';

const MODEL_CONNECTION_FAILURE =
  /llmserver generate error|model service (?:is )?unavailable|failed to (?:connect|fetch|reach)|connection (?:error|refused|reset|timed? ?out)|network (?:error|unreachable)|fetch failed|no (?:healthy|available) (?:model )?(?:worker|instance)|模型(?:服务.{0,12}|“[^”]+”)?(?:连接失败|不可用|超时)/i;

export const isModelConnectionFailure = (detail: string) => MODEL_CONNECTION_FAILURE.test(detail);

const compactErrorDetail = (detail: string) => detail.replace(/\s+/g, ' ').trim().slice(0, 500);

export const describeModelConnectionFailure = (modelName: string, detail: string, status?: number) => {
  const selectedModel = modelName.trim() || '未命名模型';
  const statusLabel = status ? `（HTTP ${status}）` : '';
  const compactDetail = compactErrorDetail(detail);
  return `模型“${selectedModel}”连接失败${statusLabel}${compactDetail ? `：${compactDetail}` : '。请检查模型服务配置和网络连接后重试。'}`;
};

export const describeModelRequestFailure = (modelName: string, detail: string, status: number) => {
  if (isModelConnectionFailure(detail) || [502, 503, 504].includes(status)) {
    return describeModelConnectionFailure(modelName, detail, status);
  }
  const selectedModel = modelName.trim() || '未命名模型';
  const compactDetail = compactErrorDetail(detail);
  return `模型“${selectedModel}”请求失败（HTTP ${status}）${compactDetail ? `：${compactDetail}` : ''}`;
};
