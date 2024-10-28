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
  domain_type: string;
}
export type AddKnowledgeParams = {
  name: string;
  vector_type: string;
  owner: string;
  desc: string;
  domain_type: string;
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
  questions?: string[];
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
  questions?: string[];
};

export type IDocumentResponse = {
  data: Array<IDocument>;
  page: number;
  total: number;
};

export type IStrategyParameter = {
  param_name: string;
  param_type: string;
  default_value?: string | number;
  description: string;
};

export type IChunkStrategyResponse = {
  strategy: string;
  name: string;
  parameters: Array<IStrategyParameter>;
  suffix: Array<string>;
  type: Array<string>;
};

export type IStrategyProps = {
  chunk_strategy: string;
  chunk_size?: number;
  chunk_overlap?: number;
};

export type ISyncBatchParameter = {
  doc_id: number;
  name?: string;
  chunk_parameters: IStrategyProps;
};

export type ISyncBatchResponse = {
  tasks: Array<number>;
};

export type ChunkListParams = {
  document_id?: string | number;
  page: number;
  page_size: number;
  content?: string;
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

export type GraphVisResult = {
  nodes: Array<any>;
  edges: Array<any>;
};

export type ArgumentsParams = {
  argument: string;
};

export type StepChangeParams = {
  label: 'forward' | 'back' | 'finish';
  spaceName?: string;
  docType?: string;
  files?: Array<File>;
  pace?: number;
};

export type File = {
  name: string;
  doc_id: number;
  status?: string;
};

export type SummaryParams = {
  doc_id: number;
  model_name: string;
  conv_uid: string;
};

export interface SearchDocumentParams {
  doc_name?: string;
  status?: string;
}
export interface AddYuqueProps {
  doc_name: string;
  content: string;
  doc_token: string;
  doc_type: string;
  space_name: string;
  questions?: string[];
}

export interface RecallTestChunk {
  chunk_id: number;
  content: string;
  metadata: Record<string, any>;
  score: number;
}

export interface RecallTestProps {
  question: string;
  recall_score_threshold?: number;
  recall_top_k?: number;
  recall_retrievers: string[];
}

export type SpaceConfig = {
  storage: IStorage;
};

export type IStorage = Array<{
  name: string;
  desc: string;
  domain_types: Array<{ name: string; desc: string }>;
}>;
