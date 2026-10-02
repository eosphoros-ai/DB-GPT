/**
 * LLM-Wiki API client (GET/PUT/DELETE + POST over the knowledge v2 prefix).
 * Endpoint contract mirrors WeKnora's wiki routes.
 */
import {
  WikiGraphResult,
  WikiIndexResult,
  WikiPage,
  WikiPageListResult,
  WikiRevision,
  WikiSearchHit,
  WikiStatusResult,
  WikiTreeResult,
} from '@/types/wiki';
import { DELETE, GET, POST, PUT } from './index';

const KB_V2_PREFIX = '/api/v2/serve/knowledge';

const wikiPrefix = (spaceId: string | number) => `${KB_V2_PREFIX}/${spaceId}/wiki`;

/** Encode each slug segment but keep the "/" separators. */
export const encodeSlugPath = (slug: string) =>
  slug
    .split('/')
    .map(segment => encodeURIComponent(segment))
    .join('/');

// ============ status ============
export const getWikiStatus = (spaceId: string | number) => {
  return GET<null, WikiStatusResult>(`${wikiPrefix(spaceId)}/status`);
};

// ============ pages ============
export const listWikiPages = (
  spaceId: string | number,
  params?: {
    page_type?: string;
    status?: string;
    query?: string;
    category?: string;
    page?: number;
    page_size?: number;
  },
) => {
  return GET<typeof params, WikiPageListResult>(`${wikiPrefix(spaceId)}/pages`, params);
};

export const createWikiPage = (
  spaceId: string | number,
  data: {
    slug?: string;
    title: string;
    content?: string;
    summary?: string;
    page_type?: string;
    category_path?: string[];
    aliases?: string[];
  },
) => {
  return POST<typeof data, WikiPage>(`${wikiPrefix(spaceId)}/pages`, data);
};

export const getWikiPage = (spaceId: string | number, slug: string) => {
  return GET<null, WikiPage>(`${wikiPrefix(spaceId)}/pages/${encodeSlugPath(slug)}`);
};

export const updateWikiPage = (
  spaceId: string | number,
  slug: string,
  data: {
    title?: string;
    content?: string;
    summary?: string;
    aliases?: string[];
    status?: string;
    /** optimistic lock; server responds 409 with the current version when stale */
    version?: number;
  },
) => {
  return PUT<typeof data, WikiPage>(`${wikiPrefix(spaceId)}/pages/${encodeSlugPath(slug)}`, data);
};

export const deleteWikiPage = (spaceId: string | number, slug: string) => {
  return DELETE<null, boolean>(`${wikiPrefix(spaceId)}/pages/${encodeSlugPath(slug)}`);
};

// ============ tree / index ============
export const getWikiTree = (spaceId: string | number) => {
  return GET<null, WikiTreeResult>(`${wikiPrefix(spaceId)}/tree`);
};

export const getWikiIndex = (spaceId: string | number) => {
  return GET<null, WikiIndexResult>(`${wikiPrefix(spaceId)}/index`);
};

// ============ revisions / revert ============
export const listWikiRevisions = (spaceId: string | number, slug: string) => {
  return GET<null, { revisions: WikiRevision[] }>(`${wikiPrefix(spaceId)}/revisions/${encodeSlugPath(slug)}`);
};

/** Fetch a single revision snapshot (with content). */
export const getWikiRevision = (spaceId: string | number, slug: string, version: number) => {
  return GET<{ version: number }, WikiRevision>(`${wikiPrefix(spaceId)}/revisions/${encodeSlugPath(slug)}`, {
    version,
  });
};

export const revertWikiPage = (spaceId: string | number, slug: string, version: number) => {
  return POST<{ slug: string; version: number }, WikiPage>(`${wikiPrefix(spaceId)}/revert`, {
    slug,
    version,
  });
};

// ============ graph / search ============
export const getWikiGraph = (
  spaceId: string | number,
  params?: { mode?: 'overview' | 'ego'; center?: string; depth?: number; limit?: number },
) => {
  return GET<typeof params, WikiGraphResult>(`${wikiPrefix(spaceId)}/graph`, params);
};

export const searchWikiPages = (spaceId: string | number, q: string, limit = 20) => {
  return GET<{ q: string; limit?: number }, { results: WikiSearchHit[] }>(`${wikiPrefix(spaceId)}/search`, {
    q,
    limit,
  });
};

// ============ enable + generation trigger ============
/** One-click: add "Wiki" to space index methods, seed wiki_config and
 * enqueue a full generation over existing documents. */
export const enableWiki = (spaceId: string | number) => {
  return POST<
    null,
    { status: string; already_enabled: boolean; generation_enqueued: boolean; queued_documents: number }
  >(`${wikiPrefix(spaceId)}/enable`);
};

export const generateWiki = (spaceId: string | number, documentIds?: number[]) => {
  return POST<{ document_ids?: number[] }, { status: string }>(`${wikiPrefix(spaceId)}/generate`, {
    document_ids: documentIds,
  });
};
