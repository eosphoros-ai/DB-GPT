import axios from '@/utils/ctx-axios';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ConfirmActionRequest, PendingConfirmation } from './types';

interface UseConfirmPollingOptions {
  isActive: boolean;
  pollInterval?: number;
}

interface UseConfirmPollingResult {
  pendingConfirmation: PendingConfirmation | null;
  approve: () => void;
  deny: () => void;
  dismiss: () => void;
}

export function useConfirmPolling({
  isActive,
  pollInterval = 2000,
}: UseConfirmPollingOptions): UseConfirmPollingResult {
  const [pendingConfirmation, setPendingConfirmation] = useState<PendingConfirmation | null>(null);
  const currentConfirmIdRef = useRef<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchPending = useCallback(async () => {
    try {
      const data = (await axios.get('/api/v2/serve/connectors/pending-confirms')) as
        | PendingConfirmation[]
        | undefined;
      if (data && data.length > 0) {
        const first = data[0];
        if (first.confirm_id !== currentConfirmIdRef.current) {
          currentConfirmIdRef.current = first.confirm_id;
          setPendingConfirmation(first);
        }
      }
    } catch {}
  }, []);

  useEffect(() => {
    if (!isActive) {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    fetchPending();
    intervalRef.current = setInterval(fetchPending, pollInterval);

    return () => {
      if (intervalRef.current !== null) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [isActive, pollInterval, fetchPending]);

  const sendConfirm = useCallback(async (approved: boolean) => {
    if (!pendingConfirmation) return;
    const body: ConfirmActionRequest = {
      confirm_id: pendingConfirmation.confirm_id,
      approved,
    };
    try {
      await axios.post('/api/v2/serve/connectors/confirm', body);
    } catch {}
    currentConfirmIdRef.current = null;
    setPendingConfirmation(null);
  }, [pendingConfirmation]);

  const approve = useCallback(() => sendConfirm(true), [sendConfirm]);
  const deny = useCallback(() => sendConfirm(false), [sendConfirm]);

  const dismiss = useCallback(() => {
    currentConfirmIdRef.current = null;
    setPendingConfirmation(null);
  }, []);

  return { pendingConfirmation, approve, deny, dismiss };
}
