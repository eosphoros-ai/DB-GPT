import { financialText } from './i18n';

/** Only interpolate bounded report identifiers into a visible retry request. */
export function financialTopicRetryPrompt(runId: string, topicId: string): string | null {
  if (!/^[a-zA-Z0-9_-]{1,64}$/.test(runId) || !/^[a-zA-Z0-9_-]{1,64}$/.test(topicId)) return null;
  return financialText('financial.retry_topic_prompt', { runId, topicId });
}
