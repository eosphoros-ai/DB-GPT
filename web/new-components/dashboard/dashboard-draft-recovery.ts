import { DashboardSchemaV1 } from '@/types/dashboard';

export interface DashboardLocalDraft {
  dashboardId: string;
  baseRevision: number;
  savedAt: string;
  schema: DashboardSchemaV1;
}

const keyFor = (dashboardId: string) => `dbgpt-dashboard-draft:${dashboardId}`;

export const readDashboardLocalDraft = (dashboardId: string): DashboardLocalDraft | null => {
  if (typeof window === 'undefined') return null;
  try {
    const value = window.localStorage.getItem(keyFor(dashboardId));
    if (!value) return null;
    const draft = JSON.parse(value) as DashboardLocalDraft;
    return draft.dashboardId === dashboardId && draft.schema ? draft : null;
  } catch {
    return null;
  }
};

export const writeDashboardLocalDraft = (dashboardId: string, baseRevision: number, schema: DashboardSchemaV1) => {
  if (typeof window === 'undefined') return;
  const draft: DashboardLocalDraft = {
    dashboardId,
    baseRevision,
    savedAt: new Date().toISOString(),
    schema,
  };
  try {
    window.localStorage.setItem(keyFor(dashboardId), JSON.stringify(draft));
  } catch {
    // Recovery is best effort. Storage quotas or privacy settings must not break editing.
  }
};

export const clearDashboardLocalDraft = (dashboardId: string) => {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.removeItem(keyFor(dashboardId));
  } catch {
    // See writeDashboardLocalDraft: failure to clean up must not break the editor.
  }
};
