/**
 * Line-level LCS diff for wiki revisions.
 * Ported from WeKnora frontend/src/utils/wikiLineDiff.ts (dependency-free).
 */

export type DiffLineType = 'same' | 'add' | 'del';

export interface DiffLine {
  type: DiffLineType;
  text: string;
}

const LCS_LINE_LIMIT = 1500;

function lcsDiff(oldLines: string[], newLines: string[]): DiffLine[] {
  const n = oldLines.length;
  const m = newLines.length;
  // DP table; guarded so pathological inputs degrade to "whole block changed"
  const table: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      table[i][j] = oldLines[i] === newLines[j] ? table[i + 1][j + 1] + 1 : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }
  const result: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (oldLines[i] === newLines[j]) {
      result.push({ type: 'same', text: oldLines[i] });
      i++;
      j++;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      result.push({ type: 'del', text: oldLines[i] });
      i++;
    } else {
      result.push({ type: 'add', text: newLines[j] });
      j++;
    }
  }
  while (i < n) {
    result.push({ type: 'del', text: oldLines[i] });
    i++;
  }
  while (j < m) {
    result.push({ type: 'add', text: newLines[j] });
    j++;
  }
  return result;
}

/** Diff two texts line by line. Common prefix/suffix is trimmed before the LCS pass. */
export function diffWikiLines(oldText: string, newText: string): DiffLine[] {
  const oldLines = (oldText ?? '').split('\n');
  const newLines = (newText ?? '').split('\n');

  // trim common prefix
  let start = 0;
  while (start < oldLines.length && start < newLines.length && oldLines[start] === newLines[start]) {
    start++;
  }
  // trim common suffix
  let endOld = oldLines.length;
  let endNew = newLines.length;
  while (endOld > start && endNew > start && oldLines[endOld - 1] === newLines[endNew - 1]) {
    endOld--;
    endNew--;
  }

  const head = oldLines.slice(0, start).map(text => ({ type: 'same' as const, text }));
  const tail = oldLines.slice(endOld).map(text => ({ type: 'same' as const, text }));

  const oldMiddle = oldLines.slice(start, endOld);
  const newMiddle = newLines.slice(start, endNew);

  if (oldMiddle.length > LCS_LINE_LIMIT || newMiddle.length > LCS_LINE_LIMIT) {
    // degrade: mark the whole middle as del + add
    return [
      ...head,
      ...oldMiddle.map(text => ({ type: 'del' as const, text })),
      ...newMiddle.map(text => ({ type: 'add' as const, text })),
      ...tail,
    ];
  }
  return [...head, ...lcsDiff(oldMiddle, newMiddle), ...tail];
}
