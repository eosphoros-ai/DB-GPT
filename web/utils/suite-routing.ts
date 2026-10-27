import type { SuiteItem, SuiteRecommendedQuestion } from '@/types/suite';

/** Resolve the example's database without silently falling back to another one. */
export function resolveSuiteQuestionDatabase<T extends { db_name: string }>(
  question: SuiteRecommendedQuestion,
  selectedDatabase: T | null,
  databases: T[],
): T | null {
  if (question.database_name) {
    return databases.find(database => database.db_name === question.database_name) ?? null;
  }
  return selectedDatabase;
}

export interface SuiteRouteHit {
  slug: string;
  score: number;
}

/**
 * Keyword scoring over enabled suites' `manifest_snapshot.routing.keywords`.
 *
 * Mirrors the backend design (data-agent-product-design §三 routing rules):
 * each keyword hit scores the suite's `specificity` (default 0.8); the highest
 * scoring suite wins.  Explicit tab selection on the home page overrides this
 * automatic routing, so this is only the *suggestion* shown in the route chip.
 */
export function scoreSuites(query: string, suites: SuiteItem[]): SuiteRouteHit | null {
  const q = (query || '').toLowerCase();
  if (!q.trim() || !suites?.length) return null;
  let best: SuiteRouteHit | null = null;
  for (const suite of suites) {
    const routing = suite.manifest_snapshot?.routing;
    const keywords = routing?.keywords ?? [];
    const specificity = typeof routing?.specificity === 'number' ? routing.specificity : 0.8;
    let hits = 0;
    for (const raw of keywords) {
      const kw = String(raw ?? '')
        .trim()
        .toLowerCase();
      if (kw && q.includes(kw)) hits += 1;
    }
    if (hits === 0) continue;
    const score = hits * specificity;
    if (!best || score > best.score) best = { slug: suite.name, score };
  }
  return best;
}

/** Locale-aware display name: EN prefers manifest display_en, else display/slug. */
export function suiteDisplayName(suite: SuiteItem, lang?: string): string {
  const snap = suite.manifest_snapshot;
  const isEn = (lang || '').toLowerCase().startsWith('en');
  if (isEn && snap?.display_en) return snap.display_en;
  return suite.display || snap?.display || suite.name;
}
