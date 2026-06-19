import {
  DebugParams,
  LlmOutVerifyParams,
  OperatePromptParams,
  PromptListResponse,
  PromptResponseVerifyProps,
  PromptTemplateLoadProps,
  PromptTemplateLoadResponse,
} from '@/types/prompt';
import { GET, POST } from '../index';

export const promptTypeTarget = (type: string) => {
  return GET<string, Record<string, string>[]>(`/prompt/type/targets?prompt_type=${type}`);
};

export const promptTemplateLoad = (props: PromptTemplateLoadProps) => {
  return POST<PromptTemplateLoadProps, PromptTemplateLoadResponse>(
    `/prompt/template/load?prompt_type=${props.prompt_type}&target=${props.target}`,
    props,
  );
};

export const promptResponseVerify = (props: PromptResponseVerifyProps) => {
  return POST<PromptResponseVerifyProps, Record<string, string>>('/prompt/response/verify', props);
};

/**
 * Create prompt
 */
export const addPrompt = (data: OperatePromptParams) => {
  return POST<OperatePromptParams, []>('/prompt/add', data);
};

/**
 * Update prompt
 */
export const updatePrompt = (data: OperatePromptParams) => {
  return POST<OperatePromptParams, []>('/prompt/update', data);
};

/**
 * Delete prompt
 */
export const deletePrompt = (data: OperatePromptParams) => {
  return POST<OperatePromptParams, null>('/prompt/delete', data);
};

/**
 * Prompt list
 */
export const getPromptList = (data: Record<string, any>) => {
  return POST<Record<string, any>, PromptListResponse>(
    `/prompt/query_page?page=${data.page}&page_size=${data.page_size}`,
    data,
  );
};

/**
 * LLM test
 */
export const llmTest = (data: DebugParams) => {
  return POST<DebugParams, Record<string, any>>('/prompt/template/debug', data);
};

/**
 * LLM output verification
 */
export const llmOutVerify = (data: LlmOutVerifyParams) => {
  return POST<LlmOutVerifyParams, Record<string, any>>('/prompt/response/verify', data);
};
