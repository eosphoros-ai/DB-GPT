/**
 * LLM-Wiki types (mirrors backend wiki_db.py / wiki_endpoints.py).
 */
export type WikiPageType = 'summary' | 'entity' | 'concept' | 'index' | 'synthesis' | 'comparison';
export type WikiEditSource = 'pipeline' | 'agent' | 'user' | 'revert';

export interface WikiPage {
  id: number;
  space_id: number;
  slug: string;
  title: string;
  page_type: WikiPageType;
  status: string;
  content: string;
  summary: string;
  aliases: string[];
  parent_slug?: string | null;
  category_path: string[];
  depth: number;
  version: number;
  last_edit_source: WikiEditSource;
  source_refs: { document_id: number; doc_name: string }[];
  chunk_refs: unknown[];
  in_links: string[];
  out_links: string[];
  gmt_created?: string | null;
  gmt_modified?: string | null;
}

/** Slim projection used by list / tree / graph payloads. */
export interface WikiPageLite {
  id: number;
  slug: string;
  title: string;
  page_type: WikiPageType;
  status: string;
  summary: string;
  parent_slug?: string | null;
  category_path: string[];
  depth: number;
  version: number;
  last_edit_source: WikiEditSource;
  gmt_modified?: string | null;
}

export interface WikiPageListResult {
  pages: WikiPageLite[];
  total: number;
}

export interface WikiCategoryNode {
  page_type: string;
  path: string[];
  count: number;
}

export interface WikiTreeResult {
  total: number;
  by_type: Record<string, number>;
  categories: WikiCategoryNode[];
}

export interface WikiRevision {
  id: number;
  page_id: number;
  version: number;
  title: string;
  summary: string;
  edit_source: WikiEditSource;
  editor?: string | null;
  gmt_created?: string | null;
  content?: string;
  aliases?: string[];
}

export interface WikiIndexGroup {
  path: string[];
  pages: WikiPageLite[];
}

export interface WikiIndexResult {
  intro: { slug: string; title: string; content: string } | null;
  groups: WikiIndexGroup[];
}

export interface WikiGraphNode {
  slug: string;
  title: string;
  page_type: WikiPageType;
  link_count: number;
}

export interface WikiGraphEdge {
  source: string;
  target: string;
}

export interface WikiGraphResult {
  nodes: WikiGraphNode[];
  edges: WikiGraphEdge[];
  meta: { mode: string; total: number; truncated: boolean };
}

export interface WikiStatusResult {
  wiki_enabled: boolean;
  granularity: string;
  pending_tasks: number;
  is_active: boolean;
  stats: {
    total_pages: number;
    pages_by_type: Record<string, number>;
    total_links: number;
    orphan_count: number;
  };
}

export interface WikiSearchHit {
  slug: string;
  title: string;
  page_type: WikiPageType;
  summary: string;
  snippet: string;
}

/** 409 conflict payload returned by the optimistic-lock guard. */
export interface WikiVersionConflict {
  message: string;
  current_version: number;
}
