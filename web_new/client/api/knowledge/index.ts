import { AddYuqueProps } from '@/types/knowledge';
import { POST } from '../index';

/**
 * 知识库编辑搜索
 */
export const searchDocumentList = (
  id: string,
  data: {
    doc_name: string;
  },
) => {
  return POST<{ doc_name: string }, { data: string[]; total: number; page: number }>(`/knowledge/${id}/document/list`, data);
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
