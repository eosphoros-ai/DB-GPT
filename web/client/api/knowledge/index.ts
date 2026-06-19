import { AddYuqueProps, RecallTestChunk, RecallTestProps, SearchDocumentParams } from '@/types/knowledge';
import { GET, POST } from '../index';

/**
 * Knowledge base document search
 */
export const searchDocumentList = (spaceName: string, data: SearchDocumentParams) => {
  return POST<SearchDocumentParams, { data: string[]; total: number; page: number }>(
    `/knowledge/${spaceName}/document/list`,
    data,
  );
};

/**
 * Upload Yuque document
 */
export const addYuque = (data: AddYuqueProps) => {
  return POST<AddYuqueProps, null>(`/knowledge/${data.space_name}/document/yuque/add`, data);
};

/**
 * Edit knowledge base chunk
 */
export const editChunk = (
  knowledgeName: string,
  data: { questions: string[]; doc_id: string | number; doc_name: string },
) => {
  return POST<{ questions: string[]; doc_id: string | number; doc_name: string }, null>(
    `/knowledge/${knowledgeName}/document/edit`,
    data,
  );
};
/**
 * Recall test recommended questions
 */
export const recallTestRecommendQuestion = (id: string) => {
  return GET<{ id: string }, string[]>(`/knowledge/${id}/recommend_questions`);
};

/**
 * Recall method options
 */
export const recallMethodOptions = (id: string) => {
  return GET<{ id: string }, string[]>(`/knowledge/${id}/recall_retrievers`);
};
/**
 * Recall test
 */
export const recallTest = (data: RecallTestProps, id: string) => {
  return POST<RecallTestProps, RecallTestChunk[]>(`/knowledge/${id}/recall_test`, data);
};

// Fuzzy search chunks
export const searchChunk = (data: { document_id: string; content: string }, name: string) => {
  return POST<{ document_id: string; content: string }, string[]>(`/knowledge/${name}/chunk/list`, data);
};

// Add questions to chunk
export const chunkAddQuestion = (data: { chunk_id: string; questions: string[] }) => {
  return POST<{ chunk_id: string; questions: string[] }, string[]>(`/knowledge/questions/chunk/edit`, data);
};
