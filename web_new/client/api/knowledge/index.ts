import { AddYuqueProps, RecallTestChunk, RecallTestProps } from '@/types/knowledge';
import { GET, POST } from '../index';
import { SearchDocumentParams } from '@/types/knowledge';

/**
 * 知识库编辑搜索
 */
export const searchDocumentList = (spaceName: string, data: SearchDocumentParams) => {
  return POST<SearchDocumentParams, { data: string[]; total: number; page: number }>(`/knowledge/${spaceName}/document/list`, data);
};

/**
 * 上传语雀文档
 */
export const addYuque = (data: AddYuqueProps) => {
  return POST<AddYuqueProps, null>(`/knowledge/${data.space_name}/document/yuque/add`, data);
};

/**
 * 编辑知识库切片
 */
export const editChunk = (knowledgeName: string, data: { questions: string[]; doc_id: string | number; doc_name: string }) => {
  return POST<{ questions: string[]; doc_id: string | number; doc_name: string }, null>(`/knowledge/${knowledgeName}/document/edit`, data);
};
/**
 * 召回测试推荐问题
 */
export const recallTestRecommendQuestion = (id: string) => {
  return GET<{ id: string }, string[]>(`/knowledge/${id}/recommend_questions`);
};

/**
 * 召回方法选项
 */
export const recallMethodOptions = (id: string) => {
  return GET<{ id: string }, string[]>(`/knowledge/${id}/recall_retrievers`);
};
/**
 * 召回测试
 */
export const recallTest = (data: RecallTestProps, id: string) => {
  return POST<RecallTestProps, RecallTestChunk[]>(`/knowledge/${id}/recall_test`, data);
};

// chunk模糊搜索
export const searchChunk = (data: { document_id: string; content: string }, name: string) => {
  return POST<{ document_id: string; content: string }, string[]>(`/knowledge/${name}/chunk/list`, data);
};

// chunk添加问题
export const chunkAddQuestion = (data: { chunk_id: string; questions: string[] }) => {
  return POST<{ chunk_id: string; questions: string[] }, string[]>(`/knowledge/questions/chunk/edit`, data);
};
