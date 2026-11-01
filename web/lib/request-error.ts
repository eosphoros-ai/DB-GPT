import { notification } from 'antd';
import axios from 'axios';

export function connectionFailureMessage(error: unknown): string | null {
  const text = error instanceof Error ? error.message : String(error || '');
  const status = axios.isAxiosError(error) ? error.response?.status : undefined;
  const code = axios.isAxiosError(error) ? error.code : undefined;
  if (code === 'ERR_CANCELED' || (error instanceof Error && error.name === 'AbortError')) return null;
  if (code === 'ECONNABORTED' || code === 'ETIMEDOUT' || /timeout|timed out/i.test(text)) {
    return '请求超时。当前内容已保留，请稍后重试；正在生成的任务可到历史记录中查看结果。';
  }
  if (status && [502, 503, 504].includes(status))
    return `DB-GPT 服务暂时不可用（HTTP ${status}），请检查后端服务后重试。`;
  if (code === 'ERR_NETWORK' || /network error|failed to fetch|load failed|network request failed/i.test(text)) {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) return '设备当前离线，请恢复网络后重试。';
    return '无法连接 DB-GPT 服务。请先检查后端是否运行；若后端可达，再检查代理地址或跨域配置。';
  }
  return null;
}

let lastFailure = { key: '', at: 0 };
export function notifyRequestError(error: unknown, fallback = '请求失败，请重试') {
  const connection = connectionFailureMessage(error);
  const description = connection || (error instanceof Error ? error.message : fallback);
  const key = connection ? 'dbgpt-connection-failure' : `dbgpt-request-${description}`;
  const now = Date.now();
  if (lastFailure.key === key && now - lastFailure.at < 5000) return;
  lastFailure = { key, at: now };
  notification.error({ key, message: connection ? '服务连接异常' : '请求失败', description, duration: 6 });
}
