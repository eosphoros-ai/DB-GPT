import { SuiteItem } from '@/types/suite';
import { GET, POST, DELETE } from '../index';

/**
 * List installed suites (enabled first).  Home scenario tabs, recommended
 * questions and the smart-routing chip all render from this registry.
 */
export const getSuites = async (): Promise<SuiteItem[]> => {
  const res = await GET<null, SuiteItem[]>('/api/v1/suites');
  return res?.data?.data ?? [];
};

/** Detail view: same row plus the package README.md text. */
export const getSuiteDetail = async (name: string): Promise<SuiteItem | null> => {
  const res = await GET<null, SuiteItem>(`/api/v1/suites/${encodeURIComponent(name)}`);
  return res?.data?.data ?? null;
};

export const setSuiteEnabled = (name: string, enabled: boolean) =>
  POST<null, SuiteItem>(`/api/v1/suites/${encodeURIComponent(name)}/${enabled ? 'enable' : 'disable'}`);

export const uninstallSuite = (name: string) =>
  DELETE<null, boolean>(`/api/v1/suites/${encodeURIComponent(name)}`);
