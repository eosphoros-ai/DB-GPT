import { GET } from '../index';

// 获取可用模型列表
export const getUsableModels = () => {
  return GET<null, Array<string>>('/api/v1/model/types');
};