export const EVENTS = { TASK_CLICK: 'task-click' } as const;
type TaskEvent = typeof EVENTS.TASK_CLICK;
type TaskListener = (data: { taskId: string }) => void;
const listeners = new Map<TaskEvent, Set<TaskListener>>();

export const ee = {
  on(event: TaskEvent, listener: TaskListener) {
    const group = listeners.get(event) ?? new Set<TaskListener>();
    group.add(listener);
    listeners.set(event, group);
  },
  off(event: TaskEvent, listener: TaskListener) {
    listeners.get(event)?.delete(listener);
  },
  emit(event: TaskEvent, data: { taskId: string }) {
    listeners.get(event)?.forEach(listener => listener(data));
  },
};
