import { GET } from '../index';

// 获取数据集列表
export const getBenchmarkDatasets = () => {
  return GET<null, any>(`/api/v2/serve/evaluate/benchmark/list_datasets`);
};

// 获取数据集下的物理表列表
export const getBenchmarkDatasetTables = (datasetId: string) => {
  return GET<null, any>(`/api/v2/serve/evaluate/benchmark/dataset/${datasetId}`);
};

// 获取表数据
export const getBenchmarkTableRows = (datasetId: string, table: string) => {
  return GET<null, any>(`/api/v2/serve/evaluate/benchmark/dataset/${datasetId}/${table}/rows`);
};
