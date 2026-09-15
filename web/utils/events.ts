export const MODELS_CHANGED_EVENT = '__db_gpt_models_changed__';

export function notifyModelsChanged() {
  if (typeof window === 'undefined') {
    return;
  }

  window.dispatchEvent(new Event(MODELS_CHANGED_EVENT));

  try {
    window.localStorage.setItem(MODELS_CHANGED_EVENT, `${Date.now()}`);
  } catch {
    // Ignore storage failures (for example, private browsing restrictions).
  }
}
