import { getUserId } from '@/utils';
import { useEffect, useState } from 'react';
import type { DashboardAnnotationDraft } from './dashboard-assistant';

export interface AssistantMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  failed?: boolean;
  annotations?: SavedDashboardAnnotation[];
}
export interface SavedDashboardAnnotation extends DashboardAnnotationDraft {
  chartType: string;
  dashboardTitle: string;
  savedAt: string;
  state: 'saved' | 'discussing' | 'sent';
  annotationIds?: string[];
}
export interface DashboardAssistantSession {
  drafts: DashboardAnnotationDraft[];
  saved: SavedDashboardAnnotation[];
  messages: AssistantMessage[];
  pending: DashboardAnnotationDraft[];
  clarification: string[];
  annotationIds: string[];
  lastRequest?: { text: string; drafts: DashboardAnnotationDraft[]; context?: string };
}
/** One source for the composer, tray count and submitted annotation attachments. */
export function sendableAnnotations(session: DashboardAssistantSession): SavedDashboardAnnotation[] {
  const active = new Map([...session.pending, ...session.drafts].map(draft => [draft.id, draft]));
  return session.saved.filter(item => item.state !== 'sent').map(item => ({ ...item, ...active.get(item.id) }));
}
const emptySession = (): DashboardAssistantSession => ({
  drafts: [],
  saved: [],
  messages: [],
  pending: [],
  clarification: [],
  annotationIds: [],
});
export function useDashboardAssistantSession(dashboardId: string) {
  const [session, setSession] = useState<DashboardAssistantSession>(emptySession);
  const [loadedKey, setLoadedKey] = useState('');
  const key = `dashboard-assistant-session:v1:${getUserId()}:${dashboardId}`;
  useEffect(() => {
    const timer = window.setTimeout(() => {
      let restored = emptySession();
      try {
        const parsed = JSON.parse(sessionStorage.getItem(key) || 'null');
        if (parsed && Array.isArray(parsed.drafts) && Array.isArray(parsed.saved) && Array.isArray(parsed.messages))
          restored = { ...restored, ...parsed };
      } catch {
        /* Keep the editor usable when storage is blocked. */
      }
      setSession(restored);
      setLoadedKey(key);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [key]);
  useEffect(() => {
    if (loadedKey !== key) return;
    try {
      sessionStorage.setItem(key, JSON.stringify(session));
    } catch {
      /* The in-memory session remains usable. */
    }
  }, [key, loadedKey, session]);
  return { session, setSession, loaded: loadedKey === key };
}
