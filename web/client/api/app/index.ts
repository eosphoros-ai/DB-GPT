import {
  AppListResponse,
  CreateAppParams,
  IAgent,
  IApp,
  NativeAppScenesResponse,
  StrategyResponse,
  TeamMode,
} from '@/types/app';

import { GET, POST } from '../index';

/**
 * 查询team_mode模式
 */
export const getTeamMode = () => {
  return GET<null, TeamMode[]>('/api/v1/team-mode/list');
};
/**
 *  创建应用
 */
export const addApp = (data: CreateAppParams) => {
  return POST<CreateAppParams, IApp>('/api/v1/app/create', data);
};
/**
 *  更新应用
 */
export const updateApp = (data: CreateAppParams) => {
  return POST<CreateAppParams, IApp>('/api/v1/app/edit', data);
};
/**
 *  应用列表
 */
export const getAppList = (data: Record<string, any>) => {
  return POST<Record<string, any>, AppListResponse>(
    `/api/v1/app/list?page=${data.page || 1}&page_size=${data.page_size || 12}`,
    data,
  );
};
/**
 *  获取创建应用agents
 */
export const getAgents = () => {
  return GET<object, IAgent[]>('/api/v1/agents/list', {});
};
/**
 *  创建auto_plan应用
 *  获取模型策略
 */
export const getAppStrategy = () => {
  return GET<null, StrategyResponse[]>(`/api/v1/llm-strategy/list`);
};
/**
 *  创建native_app应用
 *  获取资源参数
 */
export const getResource = (data: Record<string, string>) => {
  return GET<Record<string, string>, Record<string, any>[]>(`/api/v1/app/resources/list?type=${data.type}`);
};
/**
 *  创建native_app应用
 *  获取应用类型
 */
export const getNativeAppScenes = () => {
  return GET<null, NativeAppScenesResponse[]>('/api/v1/native_scenes');
};
/**
 *  创建native_app应用
 *  获取模型列表
 */
export const getAppStrategyValues = (type: string) => {
  return GET<string, string[]>(`/api/v1/llm-strategy/value/list?type=${type}`);
};

/**
 * 查询应用权限
 */
export const getAppAdmins = (appCode: string) => {
  return GET<null, string[]>(`/api/v1/app/${appCode}/admins`);
};
/**
 * 更新应用权限
 */
export const updateAppAdmins = (data: { app_code: string; admins: string[] }) => {
  return POST<{ app_code: string; admins: string[] }, null>(`/api/v1/app/admins/update`, data);
};
