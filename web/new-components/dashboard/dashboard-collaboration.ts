import { applyDashboardOperation, createDashboardCollaborationTicket } from '@/client/api';
import {
  DashboardOperationRequest,
  DashboardOperationResponse,
  DashboardParticipant,
  DashboardRecord,
  DashboardSchemaV1,
} from '@/types/dashboard';
import { useEffect, useRef, useState } from 'react';

export type CollaborationStatus = 'connecting' | 'online' | 'offline' | 'conflict';

export const resolveDashboardWebSocketUrl = (
  websocketPath: string,
  ticket: string,
  apiBaseUrl = process.env.API_BASE_URL || '',
  browserOrigin = window.location.origin,
) => {
  const httpUrl = new URL(websocketPath, apiBaseUrl || browserOrigin);
  httpUrl.protocol = httpUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  httpUrl.searchParams.set('ticket', ticket);
  return httpUrl.toString();
};

const operationId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID();
  return `operation-${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
};

export const makeDashboardSaveOperation = (
  schema: DashboardSchemaV1,
  expectedRevision: number,
  clientId: string,
  promoteToAsset = true,
): DashboardOperationRequest => ({
  operation_id: operationId(),
  client_id: clientId,
  expected_revision: expectedRevision,
  promote_to_asset: promoteToAsset,
  operations: [
    // Presentation settings were introduced in schema 1.3.  Persist the
    // version together with the widgets so a legacy dashboard can be upgraded
    // atomically instead of validating 1.3 widgets against its old version.
    { op: 'replace', path: '/schema_version', value: schema.schema_version },
    { op: 'replace', path: '/dashboard/title', value: schema.dashboard.title },
    { op: 'replace', path: '/dashboard/description', value: schema.dashboard.description },
    { op: 'replace', path: '/dashboard/theme', value: schema.dashboard.theme },
    { op: 'replace', path: '/metric_context', value: schema.metric_context },
    { op: 'replace', path: '/filters', value: schema.filters },
    { op: 'replace', path: '/widgets', value: schema.widgets },
    { op: 'replace', path: '/layouts', value: schema.layouts },
    { op: 'replace', path: '/metadata/compatibility', value: schema.metadata.compatibility },
  ],
});

const getClientId = (dashboardId: string) => {
  const key = `dbgpt-dashboard-client:${dashboardId}`;
  const stored = window.sessionStorage.getItem(key);
  if (stored) return stored;
  const value = `web-${operationId()}`;
  window.sessionStorage.setItem(key, value);
  return value;
};

interface CollaborationOptions {
  dashboardId: string;
  currentRecord: DashboardRecord;
  dirty: boolean;
  onRemoteRecord: (record: DashboardRecord) => void;
}

export const useDashboardCollaboration = ({
  dashboardId,
  currentRecord,
  dirty,
  onRemoteRecord,
}: CollaborationOptions) => {
  const [clientId, setClientId] = useState('');
  const [status, setStatus] = useState<CollaborationStatus>('connecting');
  const [participants, setParticipants] = useState<DashboardParticipant[]>([]);
  const [pendingRemote, setPendingRemote] = useState<DashboardRecord | null>(null);
  const recordRef = useRef(currentRecord);
  const dirtyRef = useRef(dirty);
  const remoteHandlerRef = useRef(onRemoteRecord);

  useEffect(() => {
    recordRef.current = currentRecord;
  }, [currentRecord]);
  useEffect(() => {
    dirtyRef.current = dirty;
  }, [dirty]);
  useEffect(() => {
    remoteHandlerRef.current = onRemoteRecord;
  }, [onRemoteRecord]);

  useEffect(() => {
    const value = getClientId(dashboardId);
    // The session-scoped browser identity is only available after mount.
    setClientId(value);
    let cancelled = false;
    let socket: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let heartbeat: ReturnType<typeof setInterval> | null = null;
    let retryDelay = 500;

    const connect = async () => {
      if (cancelled) return;
      setStatus('connecting');
      try {
        const response = await createDashboardCollaborationTicket(dashboardId, value);
        if (cancelled) return;
        const issued = response.data.data;
        socket = new WebSocket(resolveDashboardWebSocketUrl(issued.websocket_path, issued.ticket));
        socket.onopen = () => {
          retryDelay = 500;
          setStatus('online');
          heartbeat = setInterval(() => socket?.readyState === WebSocket.OPEN && socket.send('{"type":"ping"}'), 20000);
        };
        socket.onmessage = event => {
          const message = JSON.parse(event.data) as { type: string; payload?: Record<string, any> };
          if (message.type === 'presence.changed') {
            setParticipants((message.payload?.participants as DashboardParticipant[]) || []);
            return;
          }
          if (message.type === 'operation.conflict') {
            setStatus('conflict');
            return;
          }
          if (message.type !== 'operation.accepted') return;
          const responsePayload = message.payload as unknown as DashboardOperationResponse;
          if (responsePayload.operation.client_id === value) return;
          if (responsePayload.dashboard.current_revision <= recordRef.current.current_revision) return;
          if (dirtyRef.current) {
            setPendingRemote(responsePayload.dashboard);
            setStatus('conflict');
          } else {
            remoteHandlerRef.current(responsePayload.dashboard);
          }
        };
        socket.onclose = () => {
          if (heartbeat) clearInterval(heartbeat);
          if (cancelled) return;
          setStatus('offline');
          reconnectTimer = setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 5000);
        };
        socket.onerror = () => socket?.close();
      } catch {
        if (cancelled) return;
        setStatus('offline');
        reconnectTimer = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 5000);
      }
    };
    connect();
    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (heartbeat) clearInterval(heartbeat);
      socket?.close();
    };
  }, [dashboardId]);

  const save = async (schema: DashboardSchemaV1, expectedRevision: number, promoteToAsset = true) => {
    if (!clientId) throw new Error('协作连接尚未初始化，请稍后重试。');
    const response = await applyDashboardOperation(
      dashboardId,
      makeDashboardSaveOperation(schema, expectedRevision, clientId, promoteToAsset),
    );
    setStatus('online');
    setPendingRemote(null);
    return response.data.data.dashboard;
  };

  const acceptRemote = () => {
    if (!pendingRemote) return;
    remoteHandlerRef.current(pendingRemote);
    setPendingRemote(null);
    setStatus('online');
  };

  return { clientId, status, participants, pendingRemote, save, acceptRemote };
};
