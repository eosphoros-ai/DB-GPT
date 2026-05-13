import { useCallback, useEffect, useState } from 'react';
import { ConnectorCatalogEntry, ConnectorInstance, CreateConnectorRequest } from '@/new-components/connector/types';

const API_BASE = '/api/v2/serve/connectors';

async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`HTTP ${response.status}: ${text}`);
  }
  const json = await response.json();
  return json.data as T;
}

export function useConnectorTypes() {
  const [types, setTypes] = useState<ConnectorCatalogEntry[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    apiFetch<ConnectorCatalogEntry[]>(`${API_BASE}/types`)
      .then(data => setTypes(data ?? []))
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
    apiFetch<ConnectorInstance[]>(API_BASE)
      .then(data => setConnectors(data ?? []))
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
      return await apiFetch<ConnectorInstance>(API_BASE, {
        method: 'POST',
        body: JSON.stringify(data),
      });
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

  const update = useCallback(
    async (id: string, data: Partial<CreateConnectorRequest>): Promise<ConnectorInstance> => {
      setLoading(true);
      try {
        return await apiFetch<ConnectorInstance>(`${API_BASE}/${id}`, {
          method: 'PUT',
          body: JSON.stringify(data),
        });
      } catch (err) {
        console.error('Failed to update connector:', err);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { update, loading };
}

export function useDeleteConnector() {
  const [loading, setLoading] = useState(false);

  const remove = useCallback(async (id: string): Promise<void> => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/${id}`, { method: 'DELETE' });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`HTTP ${response.status}: ${text}`);
      }
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
      return await apiFetch<{ success: boolean; message: string }>(`${API_BASE}/${id}/test`, {
        method: 'POST',
      });
    } catch (err) {
      console.error('Failed to test connection:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { test, loading };
}
