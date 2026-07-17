import { getAdminCurrentUser } from '@/client/api/admin';
import { AdminUser } from '@/types/admin';
import { useRouter } from 'next/router';
import { createContext, createElement, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';

interface AdminAuthState {
  user: AdminUser | null;
  loading: boolean;
  refresh: () => Promise<void>;
}

const AdminAuthContext = createContext<AdminAuthState | null>(null);

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<AdminUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getAdminCurrentUser();
      if (!result.success || !result.data) throw new Error('Invalid authentication response');
      setUser(result.data);
    } catch {
      setUser(null);
      if (router.pathname !== '/admin/login') await router.replace('/admin/login');
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(() => ({ user, loading, refresh }), [loading, refresh, user]);

  return createElement(AdminAuthContext.Provider, { value }, children);
}

export function useAdminAuthGuard() {
  const context = useContext(AdminAuthContext);
  if (!context) throw new Error('useAdminAuthGuard must be used inside AdminAuthProvider');
  return context;
}
