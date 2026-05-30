import {
  ConnectorCatalogEntry,
  ConnectorInstance,
  ConnectorToolsResponse,
  CreateConnectorRequest,
} from '@/new-components/connector/types';
import axios from '@/utils/ctx-axios';
import { useCallback, useEffect, useState } from 'react';

const API_BASE = '/api/v2/serve/connectors';
// FastAPI registers GET / and POST / under api_prefix, so list/create require
// a trailing slash. Single-resource routes (`/{id}`, `/{id}/test`, etc.) do not.
const API_BASE_LIST = `${API_BASE}/`;

// Backend ConnectorResponse uses `connector_id`; frontend code uses `id`.
// Normalize at the boundary so the rest of the app can stay on `id`.
type BackendConnector = Omit<ConnectorInstance, 'id'> & { connector_id: string };

function normalizeConnector(raw: BackendConnector): ConnectorInstance {
  const { connector_id, ...rest } = raw;
  // `is_custom` flows through `...rest`; we coerce undefined → false so card
  // logic can rely on a boolean even on older deployments that omit the field.
  return {
    id: connector_id,
    ...rest,
    is_custom: raw.is_custom ?? false,
  } as ConnectorInstance;
}

function unwrap<T>(payload: any): T {
  // ctx-axios already unwrapped axios.response → response.data, so payload here
  // is the API envelope { success, err_code, err_msg, data }.
  return (payload?.data ?? payload) as T;
}

export function useConnectorTypes() {
  const [types, setTypes] = useState<ConnectorCatalogEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    axios
      .get(`${API_BASE}/types`)
      .then(res => setTypes(unwrap<ConnectorCatalogEntry[]>(res) ?? []))
      .catch(err => console.error('Failed to fetch connector types:', err))
      .finally(() => setLoading(false));
  }, []);

  return { types, loading };
}

export function useConnectors() {
  const [connectors, setConnectors] = useState<ConnectorInstance[]>([]);
  const [loading, setLoading] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    setLoading(true);
    axios
      .get(API_BASE_LIST)
      .then(res => {
        const raw = unwrap<BackendConnector[]>(res) ?? [];
        setConnectors(raw.map(normalizeConnector));
      })
      .catch(err => console.error('Failed to fetch connectors:', err))
      .finally(() => setLoading(false));
  }, [version]);

  const refresh = useCallback(() => {
    setVersion(v => v + 1);
  }, []);

  return { connectors, loading, refresh };
}

export function useCreateConnector() {
  const [loading, setLoading] = useState(false);

  const create = useCallback(async (data: CreateConnectorRequest): Promise<ConnectorInstance> => {
    setLoading(true);
    try {
      const res = await axios.post(API_BASE_LIST, data);
      return normalizeConnector(unwrap<BackendConnector>(res));
    } catch (err) {
      console.error('Failed to create connector:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { create, loading };
}

export function useUpdateConnector() {
  const [loading, setLoading] = useState(false);

  const update = useCallback(async (id: string, data: Partial<CreateConnectorRequest>): Promise<ConnectorInstance> => {
    setLoading(true);
    try {
      const res = await axios.put(`${API_BASE}/${id}`, data);
      return normalizeConnector(unwrap<BackendConnector>(res));
    } catch (err) {
      console.error('Failed to update connector:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { update, loading };
}

export function useDeleteConnector() {
  const [loading, setLoading] = useState(false);

  const remove = useCallback(async (id: string): Promise<void> => {
    setLoading(true);
    try {
      await axios.delete(`${API_BASE}/${id}`);
    } catch (err) {
      console.error('Failed to delete connector:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { remove, loading };
}

export function useTestConnection() {
  const [loading, setLoading] = useState(false);

  const test = useCallback(async (id: string): Promise<{ success: boolean; message: string }> => {
    setLoading(true);
    try {
      const res = await axios.post(`${API_BASE}/${id}/test`);
      return unwrap<{ success: boolean; message: string }>(res);
    } catch (err) {
      console.error('Failed to test connection:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { test, loading };
}

/**
 * Lazy hook that fetches the MCP tools list for a connector instance.
 * Caller invokes `fetch()` (or `refetch()` — same handle) when the modal opens
 * or after a retry; we deliberately do NOT auto-fetch on mount because this
 * endpoint can hit the live MCP server and we only want it on demand.
 */
export function useConnectorTools(connectorId?: string) {
  const [data, setData] = useState<ConnectorToolsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTools = useCallback(async () => {
    if (!connectorId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API_BASE}/${connectorId}/tools`);
      setData(unwrap<ConnectorToolsResponse>(res) ?? null);
    } catch (err) {
      console.error('Failed to fetch connector tools:', err);
      const message = err instanceof Error ? err.message : 'Failed to load tools';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [connectorId]);

  return { data, loading, error, refetch: fetchTools, fetch: fetchTools };
}
