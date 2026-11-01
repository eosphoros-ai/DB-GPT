import { getUserId } from '@/utils';

const key = () => `dbgpt-dashboard-visits:${getUserId()}`;
export function readDashboardVisits(): { id: string; at: number }[] {
  if (typeof window === 'undefined') return [];
  try {
    const items: unknown = JSON.parse(localStorage.getItem(key()) || '[]');
    return Array.isArray(items) ? items.filter(item => typeof item?.id === 'string' && Number.isFinite(item?.at)).slice(0, 30) : [];
  } catch { return []; }
}
export function rememberDashboardVisit(id: string) {
  try { localStorage.setItem(key(), JSON.stringify([{ id, at: Date.now() }, ...readDashboardVisits().filter(item => item.id !== id)].slice(0, 30))); }
  catch { /* Storage restrictions should never prevent opening a dashboard. */ }
}
