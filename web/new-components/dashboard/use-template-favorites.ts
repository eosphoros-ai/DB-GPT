import { useMemo, useSyncExternalStore } from 'react';

const KEY = 'dbgpt.template.favorites.v1';
const EVENT = 'dbgpt-template-favorites';
let fallback = '[]';
const snapshot = () => {
  try {
    return localStorage.getItem(KEY) || '[]';
  } catch {
    return fallback;
  }
};
const subscribe = (changed: () => void) => {
  window.addEventListener('storage', changed);
  window.addEventListener(EVENT, changed);
  return () => {
    window.removeEventListener('storage', changed);
    window.removeEventListener(EVENT, changed);
  };
};
export function useTemplateFavorites() {
  const raw = useSyncExternalStore(subscribe, snapshot, () => '[]');
  const favorites = useMemo<string[]>(() => {
    try {
      const saved: unknown = JSON.parse(raw);
      return Array.isArray(saved) ? saved.filter((id): id is string => typeof id === 'string') : [];
    } catch {
      return [];
    }
  }, [raw]);
  const toggle = (id: string) => {
    let current: string[] = [];
    try {
      const saved: unknown = JSON.parse(snapshot());
      if (Array.isArray(saved)) current = saved.filter((value): value is string => typeof value === 'string');
    } catch {
      /* Recover an invalid saved list. */
    }
    fallback = JSON.stringify(current.includes(id) ? current.filter(value => value !== id) : [...current, id]);
    try {
      localStorage.setItem(KEY, fallback);
    } catch {
      /* Keep this session usable when storage is blocked. */
    }
    window.dispatchEvent(new Event(EVENT));
  };
  return { favorites, toggle };
}
