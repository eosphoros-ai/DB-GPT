import {
  IFlow,
  IFlowExportParams,
  IFlowImportParams,
  IFlowNode,
  IFlowRefreshParams,
  IFlowResponse,
  IFlowUpdateParam,
  IGetKeysRequestParams,
  IGetKeysResponseData,
  IGetVariablesByKeyRequestParams,
  IGetVariablesByKeyResponseData,
  IUploadFileRequestParams,
  IUploadFileResponse,
} from '@/types/flow';
import { DELETE, GET, POST, PUT } from '../index';

/** AWEL Flow */
export const addFlow = (data: IFlowUpdateParam) => {
  return POST<IFlowUpdateParam, IFlow>('/api/v2/serve/awel/flows', data);
};

export const getFlows = ({ page, page_size }: { page?: number; page_size?: number }) => {
  return GET<any, IFlowResponse>('/api/v2/serve/awel/flows', {
    page,
    page_size,
  });
};

export const getFlowById = (id: string) => {
  return GET<null, IFlow>(`/api/v2/serve/awel/flows/${id}`);
};

export const updateFlowById = (id: string, data: IFlowUpdateParam) => {
  return PUT<IFlowUpdateParam, IFlow>(`/api/v2/serve/awel/flows/${id}`, data);
};

export const deleteFlowById = (id: string) => {
  return DELETE<null, null>(`/api/v2/serve/awel/flows/${id}`);
};

export const getFlowNodes = (tags?: string) => {
  return GET<{ tags?: string }, Array<IFlowNode>>(`/api/v2/serve/awel/nodes`, { tags });
};

export const refreshFlowNodeById = (data: IFlowRefreshParams) => {
  return POST<IFlowRefreshParams, IFlowNode>('/api/v2/serve/awel/nodes/refresh', data);
};

export const debugFlow = (data: any) => {
  return POST<any, IFlowNode>('/api/v2/serve/awel/flow/debug', data);
};

export const exportFlow = (data: IFlowExportParams) => {
  return GET<IFlowExportParams, any>(`/api/v2/serve/awel/flow/export/${data.uid}`, data);
};

export const importFlow = (data: IFlowImportParams) => {
  return POST<IFlowImportParams, any>('/api/v2/serve/awel/flow/import', data);
};

export const uploadFile = (data: IUploadFileRequestParams) => {
  return POST<IUploadFileRequestParams, Array<IUploadFileResponse>>('/api/v2/serve/file/files/dbgpt', data);
};

export const downloadFile = (fileId: string) => {
  return GET<null, any>(`/api/v2/serve/file/files/dbgpt/${fileId}`);
};

export const getFlowTemplateById = (id: string) => {
  return GET<null, any>(`/api/v2/serve/awel/flow/templates/${id}`);
};

export const getFlowTemplates = () => {
  return GET<null, any>(`/api/v2/serve/awel/flow/templates`);
};

export const getKeys = (data?: IGetKeysRequestParams) => {
  return GET<IGetKeysRequestParams, Array<IGetKeysResponseData>>('/api/v2/serve/awel/variables/keys', data);
};

export const getVariablesByKey = (data: IGetVariablesByKeyRequestParams) => {
  return GET<IGetVariablesByKeyRequestParams, IGetVariablesByKeyResponseData>('/api/v2/serve/awel/variables', data);
};

export const metadataBatch = (data: IUploadFileRequestParams) => {
  return POST<IUploadFileRequestParams, Array<IUploadFileResponse>>('/api/v2/serve/file/files/metadata/batch', data);
};
