/**
 * Canonical decoder for ReAct agent final answers.
 *
 * New responses carry citations as structured data next to the Markdown
 * content. The legacy `<references>` envelope is accepted here only as a
 * read adapter so rendering modules never need to parse protocol markup.
 */

export interface AgentCitation {
  index: number;
  id: string;
  sourceName: string;
  excerpt: string;
  score?: number;
  path?: string;
  url?: string;
}

export interface AgentFinalAnswer {
  content: string;
  citations: AgentCitation[];
}

const MAX_CITATIONS = 10;
const MAX_SOURCE_NAME_LENGTH = 512;
const MAX_EXCERPT_LENGTH = 2_000;
const MAX_TOTAL_EXCERPT_LENGTH = 12_000;
const MAX_LOCATION_LENGTH = 2_048;
const GENERIC_LEGACY_SOURCE_NAMES = new Set([
  'knowledge base',
  'knowledgebase',
  'knowledge',
  'kb',
  '知识库',
  'reference',
  'references',
  'source',
  'unknown',
]);

type UnknownRecord = Record<string, unknown>;

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isHistoryEnvelope(value: unknown): value is UnknownRecord {
  if (!isRecord(value) || value.type !== 'react-agent') return false;
  return value.version === 1 || value.protocol_version === 2;
}

function firstString(record: UnknownRecord, keys: string[]): string | undefined {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return undefined;
}

function optionalString(value: unknown, maxLength: number): string | undefined {
  if (typeof value !== 'string') return undefined;
  const normalized = value.trim();
  return normalized ? normalized.slice(0, maxLength) : undefined;
}

function optionalNumber(value: unknown): number | undefined {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim()) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return undefined;
}

function normalizeCitation(
  value: unknown,
  fallbackIndex: number,
  sourceNameFallback?: string,
  excerptLimit = MAX_EXCERPT_LENGTH,
): AgentCitation | null {
  if (!isRecord(value)) return null;

  const sourceName =
    firstString(value, ['sourceName', 'source_name', 'name', 'title', 'document_name', 'doc_name']) ??
    sourceNameFallback;
  const excerpt = firstString(value, ['excerpt', 'content', 'text']);
  if (!sourceName || !excerpt) return null;

  const rawIndex = optionalNumber(value.index);
  const index = rawIndex && Number.isInteger(rawIndex) && rawIndex > 0 ? rawIndex : fallbackIndex;
  const rawId = value.id;
  const id =
    (typeof rawId === 'string' && rawId.trim()) ||
    (typeof rawId === 'number' && Number.isFinite(rawId) ? String(rawId) : `${sourceName}:${index}`);
  const score = optionalNumber(value.score ?? value.recall_score);
  const path = optionalString(value.path ?? value.source_path ?? value.file_path, MAX_LOCATION_LENGTH);
  const url = optionalString(value.url ?? value.source_url, MAX_LOCATION_LENGTH);

  return {
    index,
    id: String(id),
    sourceName: sourceName.slice(0, MAX_SOURCE_NAME_LENGTH),
    excerpt: excerpt.slice(0, Math.min(MAX_EXCERPT_LENGTH, excerptLimit)),
    ...(score !== undefined && { score }),
    ...(path && { path }),
    ...(url && { url }),
  };
}

function normalizeStructuredCitations(value: unknown): AgentCitation[] {
  if (!Array.isArray(value)) return [];

  const citations: AgentCitation[] = [];
  const seen = new Set<string>();
  let remainingExcerptLength = MAX_TOTAL_EXCERPT_LENGTH;
  for (const item of value) {
    if (citations.length >= MAX_CITATIONS || remainingExcerptLength <= 0) break;
    const citation = normalizeCitation(item, citations.length + 1, undefined, remainingExcerptLength);
    if (!citation) continue;
    const key = `${citation.index}:${citation.id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    citations.push(citation);
    remainingExcerptLength -= citation.excerpt.length;
  }
  return citations;
}

function normalizeLegacyReferences(value: unknown): AgentCitation[] {
  if (!Array.isArray(value)) return [];

  const citations: AgentCitation[] = [];
  const seen = new Set<string>();
  let remainingExcerptLength = MAX_TOTAL_EXCERPT_LENGTH;
  for (const group of value) {
    if (!isRecord(group) || !Array.isArray(group.chunks)) continue;
    const groupSourceName = legacyDocumentIdentity(group);
    const groupPath = firstString(group, ['path', 'source_path', 'file_path']);
    const groupUrl = firstString(group, ['url', 'source_url']);

    for (const chunk of group.chunks) {
      if (citations.length >= MAX_CITATIONS || remainingExcerptLength <= 0) return citations;
      if (!isRecord(chunk)) continue;

      const chunkSourceName = legacyDocumentIdentity(chunk);
      const path = firstString(chunk, ['path', 'source_path', 'file_path']) ?? groupPath;
      const url = firstString(chunk, ['url', 'source_url']) ?? groupUrl;
      const specificSourceName = chunkSourceName ?? groupSourceName;

      // The old ReAct producer labelled every tool observation as
      // "Knowledge Base", including source code and SQL output. Such data is
      // useful only for stripping the legacy envelope; it is not trustworthy
      // citation metadata. Surface a legacy citation only when the payload
      // identifies a concrete document, path, or URL.
      const trustedSourceName = specificSourceName ?? path ?? url;
      if (!trustedSourceName) continue;

      const citation = normalizeCitation(
        {
          ...chunk,
          // Override a generic chunk label when its path/URL is the actual,
          // concrete source identity.
          sourceName: trustedSourceName,
          ...(path && { path }),
          ...(url && { url }),
        },
        citations.length + 1,
        undefined,
        remainingExcerptLength,
      );
      if (!citation) continue;
      const key = `${citation.index}:${citation.id}`;
      if (seen.has(key)) continue;
      seen.add(key);
      citations.push(citation);
      remainingExcerptLength -= citation.excerpt.length;
    }
  }
  return citations;
}

function isSpecificLegacySourceName(value: string | undefined): value is string {
  if (!value) return false;
  const normalized = value.trim().toLocaleLowerCase();
  if (GENERIC_LEGACY_SOURCE_NAMES.has(normalized)) return false;
  return (
    normalized.includes('/') ||
    normalized.includes('\\') ||
    /\.(?:md|mdx|txt|pdf|docx?|html?|csv|tsv|xlsx?|json|ya?ml|py|ipynb|js|jsx|ts|tsx|sql|rst)$/i.test(normalized)
  );
}

function legacyDocumentIdentity(record: UnknownRecord): string | undefined {
  const explicitDocumentName = firstString(record, ['document_name', 'doc_name']);
  if (explicitDocumentName) return explicitDocumentName;
  const label = firstString(record, ['sourceName', 'source_name', 'name', 'title']);
  return isSpecificLegacySourceName(label) ? label : undefined;
}

function decodeXmlAttribute(value: string): string {
  return value
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

/**
 * Split the exact, trailing legacy envelope from user-visible Markdown.
 *
 * The old producer wrapped raw JSON in a single-quoted attribute. JSON
 * strings may themselves contain apostrophes, so the closing quote is read
 * from the end of the known envelope instead of stopping at the first quote.
 */
function splitLegacyReferences(content: string): { content: string; citations: AgentCitation[] } {
  const trimmedEnd = content.trimEnd();
  const openingPattern = /<references\b\s+title\s*=\s*(["'])References\1\s+references\s*=\s*(["'])/gi;
  const markerIndexes: number[] = [];
  let openingMatch: RegExpExecArray | null;
  while ((openingMatch = openingPattern.exec(trimmedEnd)) !== null) {
    markerIndexes.push(openingMatch.index);
  }
  if (markerIndexes.length === 0) return { content, citations: [] };

  const candidates: Array<{ markerIndex: number; match: RegExpMatchArray }> = [];
  for (const candidateIndex of markerIndexes) {
    const candidate = trimmedEnd.slice(candidateIndex);
    const match = candidate.match(
      /^<references\b\s+title\s*=\s*(["'])References\1\s+references\s*=\s*(["'])([\s\S]*)\2\s*(?:>\s*<\/references\s*>|\/>)$/i,
    );
    if (match) {
      candidates.push({ markerIndex: candidateIndex, match });
    }
  }
  if (candidates.length === 0) return { content, citations: [] };

  // Prefer the outermost candidate whose attribute is valid JSON. This is
  // important because a cited excerpt can itself contain an exact
  // `<references ...>` example. Looking only for the last opening marker
  // would then expose the beginning of the outer metadata envelope.
  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(decodeXmlAttribute(candidate.match[3]));
      return {
        content: trimmedEnd.slice(0, candidate.markerIndex).trimEnd(),
        citations: normalizeLegacyReferences(parsed),
      };
    } catch {
      // A later candidate may be the real outer envelope.
    }
  }

  // Fail closed: if the trailing envelope is structurally complete but its
  // metadata is malformed, remove the whole outermost envelope and expose no
  // citation data.
  return {
    content: trimmedEnd.slice(0, candidates[0].markerIndex).trimEnd(),
    citations: [],
  };
}

/** Decode a live SSE `final` payload or a plain legacy final string. */
export function decodeFinalEvent(payload: unknown): AgentFinalAnswer {
  const record = isRecord(payload) ? payload : null;
  const rawContent = typeof payload === 'string' ? payload : typeof record?.content === 'string' ? record.content : '';
  const legacy = splitLegacyReferences(rawContent);
  const structured = normalizeStructuredCitations(record?.citations);

  return {
    content: legacy.content,
    citations: structured.length > 0 ? structured : legacy.citations,
  };
}

/** Decode a persisted history payload while retaining plain-string history. */
export function decodeHistoryAnswer(payload: unknown): AgentFinalAnswer {
  let value = payload;
  if (typeof payload === 'string') {
    const trimmed = payload.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
      try {
        const parsed = JSON.parse(trimmed);
        if (isHistoryEnvelope(parsed)) {
          value = parsed;
        }
      } catch {
        // Plain Markdown that happens to start with "{" remains plain text.
      }
    }
  }

  if (!isHistoryEnvelope(value)) return decodeFinalEvent(payload);
  return decodeFinalEvent({
    content: typeof value.final_content === 'string' ? value.final_content : value.content,
    citations: value.citations,
  });
}

// Explicit aliases keep existing/new callers readable without duplicating
// decoding behaviour at separate call sites.
export const decodeAgentFinalAnswer = decodeFinalEvent;
export const decodeAgentHistoryAnswer = decodeHistoryAnswer;
