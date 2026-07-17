import { AdminResult, AuditEvent, AuditEventListParams, Page } from '@/types/admin';
import api from '@/utils/ctx-axios';

const AUDIT_BASE = '/api/v1/admin/audit';

export const getAuditEvents = (params: AuditEventListParams = {}) =>
  api.get<unknown, AdminResult<Page<AuditEvent>>>(AUDIT_BASE, { params });

export const getAuditEventDetail = (eventId: string) =>
  api.get<unknown, AdminResult<AuditEvent>>(`${AUDIT_BASE}/${encodeURIComponent(eventId)}`);
