import axios from '@/utils/ctx-axios';
import { ConnectorCatalogEntry, ConnectorInstance, CreateConnectorRequest } from '@/new-components/connector/types';
import { useCallback, useEffect, useState } from 'react';

const API_BASE = '/api/v2/serve/connectors';

// Backend ConnectorResponse uses `connector_id`; frontend code uses `id`.
// Normalize at the boundary so the rest of the app can stay on `id`.
type BackendConnector = Omit<ConnectorInstance, 'id'> & { connector_id: string };

function normalizeConnector(raw: BackendConnector): ConnectorInstance {
  const { connector_id, ...rest } = raw;
  return { id: connector_id, ...rest } as ConnectorInstance;
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
      .get(API_BASE)
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
      const res = await axios.post(API_BASE, data);
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

  const update = useCallback(
    async (id: string, data: Partial<CreateConnectorRequest>): Promise<ConnectorInstance> => {
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
