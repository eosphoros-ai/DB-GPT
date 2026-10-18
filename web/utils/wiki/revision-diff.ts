/**
 * Field-level revision diff assembly.
 * Ported from WeKnora frontend/src/utils/wikiRevisionDiff.ts.
 */
import { diffWikiLines } from './line-diff';

export interface WikiRevisionSnapshot {
  title?: string | null;
  summary?: string | null;
  content?: string | null;
}

export interface WikiRevisionDiffSection {
  field: 'title' | 'summary' | 'content';
  lines: { type: 'same' | 'add' | 'del'; text: string }[];
}

/** Diff two revision snapshots field by field; unchanged fields are omitted. */
export function diffWikiRevision(
  oldSnap: WikiRevisionSnapshot,
  newSnap: WikiRevisionSnapshot,
): WikiRevisionDiffSection[] {
  const sections: WikiRevisionDiffSection[] = [];
  const fields: (keyof WikiRevisionSnapshot)[] = ['title', 'summary', 'content'];
  for (const field of fields) {
    const oldValue = oldSnap[field] ?? '';
    const newValue = newSnap[field] ?? '';
    if (oldValue === newValue) continue;
    sections.push({ field, lines: diffWikiLines(oldValue, newValue) });
  }
  return sections;
}
