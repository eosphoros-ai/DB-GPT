import { GET } from '../index';

// 获取评测结果详情
export const getBenchmarkResultDetail = (evaluateCode: string) => {
  return GET<null, any>(`/api/v2/serve/evaluate/benchmark/result/${evaluateCode}`);
};