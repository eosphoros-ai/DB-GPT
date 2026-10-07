export interface DashboardAnnotationHandoff {
  annotationId: string;
  dashboardId: string;
  conversationId: string;
  modelPrompt: string;
  visiblePrompt: string;
  createdAt: string;
}

const handoffKey = (annotationId: string) => `dbgpt-dashboard-annotation-handoff:${annotationId}`;

export const writeDashboardAnnotationHandoff = (handoff: DashboardAnnotationHandoff) => {
  if (typeof window === 'undefined') return;
  window.sessionStorage.setItem(handoffKey(handoff.annotationId), JSON.stringify(handoff));
};

export const readDashboardAnnotationHandoff = (annotationId: string): DashboardAnnotationHandoff | null => {
  if (typeof window === 'undefined') return null;
  const raw = window.sessionStorage.getItem(handoffKey(annotationId));
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as DashboardAnnotationHandoff;
    if (
      parsed.annotationId !== annotationId ||
      !parsed.dashboardId ||
      !parsed.conversationId ||
      !parsed.modelPrompt ||
      !parsed.visiblePrompt
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
};

export const clearDashboardAnnotationHandoff = (annotationId: string) => {
  if (typeof window === 'undefined') return;
  window.sessionStorage.removeItem(handoffKey(annotationId));
};
