import { GET } from '../index';

// Get dataset list
export const getBenchmarkDatasets = () => {
  return GET<null, any>(`/api/v2/serve/evaluate/benchmark/list_datasets`);
};

// Get physical table list under a dataset
export const getBenchmarkDatasetTables = (datasetId: string) => {
  return GET<null, any>(`/api/v2/serve/evaluate/benchmark/dataset/${datasetId}`);
};

// Get table data
export const getBenchmarkTableRows = (datasetId: string, table: string) => {
  return GET<null, any>(`/api/v2/serve/evaluate/benchmark/dataset/${datasetId}/${table}/rows`);
};
