import { connectionFailureMessage } from '@/lib/request-error';
import { DashboardValidationIssue, DashboardWidget } from '@/types/dashboard';
import axios from 'axios';

export interface MissingPublicationBindingGroup {
  missingWidgets: Pick<DashboardWidget, 'id' | 'title'>[];
  otherIssues: DashboardValidationIssue[];
}

export const groupMissingPublicationBindings = (
  issues: DashboardValidationIssue[],
  widgets: Pick<DashboardWidget, 'id' | 'title'>[],
): MissingPublicationBindingGroup => {
  const widgetById = new Map(widgets.map(widget => [widget.id, widget]));
  const missingIds = new Set<string>();
  const otherIssues: DashboardValidationIssue[] = [];

  issues.forEach(issue => {
    const match =
      issue.code === 'publication_binding_required' ? /^widgets\.(.+)\.publication$/.exec(issue.path) : null;
    if (!match || !widgetById.has(match[1])) {
      otherIssues.push(issue);
      return;
    }
    missingIds.add(match[1]);
  });

  return {
    missingWidgets: widgets.filter(widget => missingIds.has(widget.id)),
    otherIssues,
  };
};

const detailMessages = (detail: unknown): string[] => {
  if (typeof detail === 'string') {
    try {
      const normalized = detail
        .replace(/'/g, '"')
        .replace(/\bFalse\b/g, 'false')
        .replace(/\bTrue\b/g, 'true');
      const parsed = JSON.parse(normalized);
      const nested = detailMessages(parsed);
      if (nested.length) return nested;
    } catch {
      // Keep the original server message when it is not JSON-like.
    }
    const embeddedMessages = [...detail.matchAll(/["'](?:message|msg)["']\s*:\s*["']([^"']+)["']/g)].map(
      match => match[1],
    );
    if (embeddedMessages.length) return embeddedMessages;
    return [detail];
  }
  if (Array.isArray(detail)) return detail.flatMap(detailMessages).filter(Boolean);
  if (!detail || typeof detail !== 'object') return [];
  if ('issues' in detail && Array.isArray(detail.issues)) return detail.issues.flatMap(detailMessages).filter(Boolean);
  if ('message' in detail && detail.message) return [String(detail.message)];
  if ('msg' in detail && detail.msg) return [String(detail.msg)];
  return [];
};

export const describeDashboardError = (error: unknown, fallback: string) => {
  const connection = connectionFailureMessage(error);
  if (connection) return connection;
  if (!axios.isAxiosError(error)) return error instanceof Error && error.message ? error.message : fallback;
  const payload = error.response?.data;
  const messages = detailMessages(payload?.detail ?? payload?.err_msg ?? payload);
  if (messages.length) return messages.join('；');
  return error.message || fallback;
};
