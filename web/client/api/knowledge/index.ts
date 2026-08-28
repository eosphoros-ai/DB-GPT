import {
  AddYuqueProps,
  KbLsJsonResponse,
  KnowledgeSpaceStats,
  RecallTestChunk,
  RecallTestProps,
  SearchDocumentParams,
} from '@/types/knowledge';
import { GET, POST } from '../index';

/**
 * 知识库编辑搜索
 */
export const searchDocumentList = (spaceName: string, data: SearchDocumentParams) => {
  return POST<SearchDocumentParams, { data: string[]; total: number; page: number }>(
    `/knowledge/${spaceName}/document/list`,
    data,
  );
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

// ============ Git 仓库同步 API (v2) ============

const KB_V2_PREFIX = '/api/v2/serve/knowledge';

export interface GitRepoSyncParams {
  repo_url: string;
  branch: string;
  exclude_dirs?: string[];
  exclude_extensions?: string[];
  include_dirs?: string[];
  build_graph?: boolean;
  chunk_strategy?: string;
}

export interface GitRepoSyncResult {
  status: string;
  head_commit?: string;
  total_files?: number;
  indexed?: number;
  skipped?: number;
  failed?: number;
  added?: number;
  modified?: number;
  deleted?: number;
}

export interface GitRepoSyncStatus {
  status: string;
  total_files: number;
  finished: number;
  running: number;
  failed: number;
  todo: number;
  last_sync_commit?: string | null;
  last_sync_time?: string | null;
  last_sync_mode?: string | null;
  repo_url?: string | null;
  branch?: string | null;
}

/** 同步 Git 仓库到知识空间（服务端 clone 模式） */
export const syncGitRepo = (spaceId: string | number, data: GitRepoSyncParams) => {
  return POST<GitRepoSyncParams, GitRepoSyncResult>(`${KB_V2_PREFIX}/${spaceId}/git/sync`, data);
};

/** 增量同步 Git 仓库 */
export const incrementalSyncGitRepo = (
  spaceId: string | number,
  data: { repo_url: string; branch: string; last_commit?: string },
) => {
  return POST<{ repo_url: string; branch: string; last_commit?: string }, GitRepoSyncResult>(
    `${KB_V2_PREFIX}/${spaceId}/git/incremental-sync`,
    data,
  );
};

/** 查询 Git 仓库同步状态 */
export const getGitSyncStatus = (spaceId: string | number) => {
  return GET<null, GitRepoSyncStatus>(`${KB_V2_PREFIX}/${spaceId}/git/sync-status`);
};

// ============ 搜索工具 API (v2) ============

export interface KbSearchParams {
  knowledge_id?: string;
  query?: string;
  path?: string;
  file_pattern?: string;
  start_line?: number;
  end_line?: number;
  offset?: number;
  limit?: number;
  top_k?: number;
  score_threshold?: number;
}

/** kb_ls - 列出知识库目录 */
export const kbLs = (spaceId: string | number, data: KbSearchParams) => {
  return POST<KbSearchParams, string>(`${KB_V2_PREFIX}/${spaceId}/tools/ls`, data);
};

/** kb_glob - 按文件名搜索 */
export const kbGlob = (spaceId: string | number, data: KbSearchParams) => {
  return POST<KbSearchParams, string>(`${KB_V2_PREFIX}/${spaceId}/tools/glob`, data);
};

/** kb_grep - 按内容关键词搜索 */
export const kbGrep = (spaceId: string | number, data: KbSearchParams) => {
  return POST<KbSearchParams, string>(`${KB_V2_PREFIX}/${spaceId}/tools/grep`, data);
};

/** kb_cat - 读取文件内容 */
export const kbCat = (spaceId: string | number, data: KbSearchParams) => {
  return POST<KbSearchParams, string>(`${KB_V2_PREFIX}/${spaceId}/tools/cat`, data);
};

/** kb_semantic_search - 语义搜索 */
export const kbSemanticSearch = (spaceId: string | number, data: KbSearchParams) => {
  return POST<KbSearchParams, string>(`${KB_V2_PREFIX}/${spaceId}/tools/semantic_search`, data);
};

// ============ 知识空间统计 API (v2) ============

/** 获取知识空间聚合统计信息 */
export const getKnowledgeSpaceStats = (spaceId: string | number) => {
  return GET<null, KnowledgeSpaceStats>(`${KB_V2_PREFIX}/${spaceId}/stats`);
};

// ============ 结构化目录列表 API (v2) ============

/** 获取知识空间结构化目录列表（JSON格式） */
export const kbLsJson = (spaceId: string | number, data?: { path?: string; offset?: number; limit?: number }) => {
  return POST<{ path?: string; offset?: number; limit?: number }, KbLsJsonResponse>(
    `${KB_V2_PREFIX}/${spaceId}/tools/ls-json`,
    data ?? {},
  );
};

// ============ 知识图谱构建 API (v2) ============

export interface KnowledgeGraphBuildResult {
  vertices: number;
  edges: number;
  files_processed: number;
  status: string;
}

/** 构建知识空间的结构图谱（代码结构 / Markdown 标题层级） */
export const buildKnowledgeGraph = (spaceId: string | number) => {
  return POST<null, KnowledgeGraphBuildResult>(`${KB_V2_PREFIX}/${spaceId}/build-graph`);
};
