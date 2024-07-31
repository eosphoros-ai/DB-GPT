import { GET, POST, DELETE } from '../index';
import type {
  getDataSetsRequest,
  getEvaluationsRequest,
  delDataSetRequest,
  delEvaluationRequest,
  uploadDataSetsRequest,
  createEvaluationsRequest,
  getMetricsRequest,
  updateDataSetRequest,
  downloadEvaluationRequest,
} from '@/types/evaluate';

export const getTestAuth = () => {
  return GET(`/api/v1/evaluate/test_auth`);
};

export const getDataSets = (data: getDataSetsRequest) => {
  return GET<getDataSetsRequest, Record<string, any>>(`/api/v1/evaluate/datasets`, data);
};
export const uploadDataSets = (data: uploadDataSetsRequest) => {
  return POST<uploadDataSetsRequest, Record<string, any>>(`/api/v1/evaluate/dataset/upload`, data, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};
export const uploadDataSetsContent = (data: uploadDataSetsRequest) => {
  return POST<uploadDataSetsRequest, Record<string, any>>(`/api/v1/evaluate/dataset/upload/content`, data);
};
export const uploadDataSetsFile = (data: FormData) => {
  return POST<FormData, Record<string, any>>(`/api/v1/evaluate/dataset/upload/file`, data, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
};

export const delDataSet = (params: delDataSetRequest) => {
  return DELETE<delDataSetRequest, Record<string, any>>(`/api/v1/evaluate/dataset`, params);
};
//download dataSet
export const downloadDataSet = (params: delDataSetRequest) => {
  return GET<delDataSetRequest, { data: BlobPart }>(`/api/v1/evaluate/dataset/download`, params, {
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    },
    responseType: 'blob',
  });
};
//download evaluation
export const downloadEvaluation = (params: downloadEvaluationRequest) => {
  return GET<downloadEvaluationRequest, { data: BlobPart }>(`/api/v1/evaluate/evaluation/result/download`, params, {
    headers: {
      'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    },
    responseType: 'blob',
  });
};
//delete evaluation
export const delEvaluation = (params: delEvaluationRequest) => {
  return DELETE<delEvaluationRequest, Record<string, any>>(`/api/v1/evaluate/evaluation`, params);
};
//get evaluations
export const getEvaluations = (data: getEvaluationsRequest) => {
  return GET<getEvaluationsRequest, Record<string, any>>(`/api/v1/evaluate/evaluations`, data);
};
export const getMetrics = (data: getMetricsRequest) => {
  return GET<getMetricsRequest, Record<string, any>>(`/api/v1/evaluate/metrics`, data);
};
export const showEvaluation = (data: Partial<createEvaluationsRequest>) => {
  return GET<Partial<createEvaluationsRequest>, Record<string, any>[]>(`/api/v1/evaluate/evaluation/detail/show`, data);
};
export const getStorageTypes = () => {
  return GET<undefined, Record<string, any>>(`/api/v1/evaluate/storage/types`, undefined);
};

//create evaluations
export const createEvaluations = (data: createEvaluationsRequest) => {
  return POST<createEvaluationsRequest, Record<string, any>>(`/api/v1/evaluate/start`, data);
};
//update evaluations
export const updateEvaluations = (data: updateDataSetRequest) => {
  return POST<updateDataSetRequest, Record<string, any>>(`/api/v1/evaluate/dataset/members/update`, data);
};

// export const cancelFeedback = (data: CancelFeedbackAddParams) => {
//   return POST<CancelFeedbackAddParams, Record<string, any>>(`/api/v1/conv/feedback/cancel`, data);
// };
