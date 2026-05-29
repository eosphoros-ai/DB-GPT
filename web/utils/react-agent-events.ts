const REACT_AGENT_NEW_TASK_EVENT = 'dbgpt:react-agent:new-task';
const REACT_AGENT_DIALOGUES_CHANGED_EVENT = 'dbgpt:react-agent:dialogues-changed';

type Unsubscribe = () => void;

function dispatchBrowserEvent(eventName: string) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(eventName));
}

function subscribeBrowserEvent(eventName: string, handler: () => void): Unsubscribe {
  if (typeof window === 'undefined') return () => {};

  const listener = () => handler();
  window.addEventListener(eventName, listener);
  return () => window.removeEventListener(eventName, listener);
}

export function dispatchReactAgentNewTask() {
  dispatchBrowserEvent(REACT_AGENT_NEW_TASK_EVENT);
}

export function subscribeReactAgentNewTask(handler: () => void): Unsubscribe {
  return subscribeBrowserEvent(REACT_AGENT_NEW_TASK_EVENT, handler);
}

export function dispatchReactAgentDialoguesChanged() {
  dispatchBrowserEvent(REACT_AGENT_DIALOGUES_CHANGED_EVENT);
}

export function subscribeReactAgentDialoguesChanged(handler: () => void): Unsubscribe {
  return subscribeBrowserEvent(REACT_AGENT_DIALOGUES_CHANGED_EVENT, handler);
}
