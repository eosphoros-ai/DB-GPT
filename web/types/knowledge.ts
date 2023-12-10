import { type } from 'os';

export interface ISpace {
  context?: any;
  desc: string;
  docs: string | number;
  gmt_created: string;
  gmt_modified: string;
  id: string | number;
  name: string;
  owner: string;
  vector_type: string;
}
export type AddKnowledgeParams = {
  name: string;
  vector_type: string;
  owner: string;
  desc: string;
};

export type BaseDocumentParams = {
  doc_name: string;
  content: string;
  doc_type: string;
};

export type Embedding = {
  chunk_overlap: string | number;
  chunk_size: string | number;
  model: string;
  recall_score: string | number;
  recall_type: string;
  topk: string;
};

export type Prompt = {
  max_token: string | number;
  scene: string;
  template: string;
};

export type Summary = {
  max_iteration: number;
  concurrency_limit: number;
};
export type IArguments = {
  embedding: Embedding;
  prompt: Prompt;
  summary: Summary;
};

export type DocumentParams = {
  doc_name: string;
  source?: string;
  content: string;
  doc_type: string;
};

export type IDocument = {
  doc_name: string;
  source?: string;
  content: string;
  doc_type: string;
  chunk_size: string | number;
  gmt_created: string;
  gmt_modified: string;
  id: number;
  last_sync: string;
  result: string;
  space: string;
  status: string;
  vector_ids: string;
};

export type IDocumentResponse = {
  data: Array<IDocument>;
  page: number;
  total: number;
};

export type ChunkListParams = {
  document_id?: string | number;
  page: number;
  page_size: number;
};

export type IChunk = {
  content: string;
  doc_name: string;
  doc_type: string;
  document_id: string | number;
  gmt_created: string;
  gmt_modified: string;
  id: string | number;
  meta_info: string;
  recall_score?: string | number;
};
export type IChunkList = {
  data: Array<IChunk>;
  page: number;
  total: number;
};

export type ArgumentsParams = {
  argument: string;
};

export type StepChangeParams = {
  label: 'forward' | 'back' | 'finish';
  spaceName?: string;
  docType?: string;
};

export type SummaryParams = {
  doc_id: number;
  model_name: string;
  conv_uid: string;
};
