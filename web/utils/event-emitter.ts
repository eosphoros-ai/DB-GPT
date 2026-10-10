export const EVENTS = { TASK_CLICK: 'task-click' } as const;
type TaskEvent = typeof EVENTS.TASK_CLICK;
type TaskListener = (data: { taskId: string }) => void;
const listeners = new Map<TaskEvent, Set<TaskListener>>();

export const ee = {
  /** Subscribe a task-click listener and return an idempotent cleanup function for component unmount. */
  on(event: TaskEvent, listener: TaskListener) {
    const group = listeners.get(event) ?? new Set<TaskListener>();
    group.add(listener);
    listeners.set(event, group);
    return () => {
      ee.off(event, listener);
    };
  },
  /** Remove this listener and discard an empty listener group without affecting other subscribers. */
  off(event: TaskEvent, listener: TaskListener) {
    const group = listeners.get(event);
    group?.delete(listener);
    if (group?.size === 0) listeners.delete(event);
  },
  /** Synchronously deliver the task event to its current subscribers. */
  emit(event: TaskEvent, data: { taskId: string }) {
    listeners.get(event)?.forEach(listener => listener(data));
  },
};
