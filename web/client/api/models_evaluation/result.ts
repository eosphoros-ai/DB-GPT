import { GET } from '../index';

// Get evaluation result details
export const getBenchmarkResultDetail = (evaluateCode: string) => {
  return GET<string, any>(`/api/v2/serve/evaluate/benchmark/result/${evaluateCode}`);
};
