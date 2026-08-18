/** Cross-layout events for the ReAct chat page and sidebar. */

export const RESET_CHAT_EVENT = 'dbgpt:reset-chat';
export const REFRESH_DIALOGUE_LIST_EVENT = 'dbgpt:refresh-dialogue-list';

export function dispatchResetChat() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(RESET_CHAT_EVENT));
}

export function dispatchRefreshDialogueList() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(REFRESH_DIALOGUE_LIST_EVENT));
}
