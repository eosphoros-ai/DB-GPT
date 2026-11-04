import type { SuiteCommand, SuiteItem } from '@/types/suite';
import { suiteDisplayName } from './suite-routing';

export interface SuiteCommandOption {
  key: string;
  suite: SuiteItem;
  command: SuiteCommand;
  suiteLabel: string;
  label: string;
  description: string;
}

export interface SuiteCommandGroup {
  suite: SuiteItem;
  label: string;
  options: SuiteCommandOption[];
}

/** Only a leading slash token opens the menu; paths and command arguments do not. */
export function getSuiteCommandQuery(value: string, caret = value.length): string | null {
  if (caret < 0 || caret > value.length) return null;
  const beforeCaret = value.slice(0, caret);
  const match = /^\s*\/([^\s/\\]*)$/.exec(beforeCaret);
  const restOfToken = value.slice(caret).split(/\s/, 1)[0];
  if (/[/\\]/.test(restOfToken)) return null;
  return match ? match[1] : null;
}

/** Keep command identity scoped to its suite, even when two suites share a name. */
export function suiteCommandKey(suite: SuiteItem, command: SuiteCommand): string {
  return `${encodeURIComponent(suite.name)}:${encodeURIComponent(command.name)}`;
}

export function getSuiteCommandGroups(suites: SuiteItem[], query = '', locale = 'zh'): SuiteCommandGroup[] {
  const isEnglish = locale.toLowerCase().startsWith('en');
  const terms = query.trim().replace(/^\//, '').toLocaleLowerCase().split(/\s+/).filter(Boolean);
  const seen = new Set<string>();
  const groups: SuiteCommandGroup[] = [];

  for (const suite of suites) {
    if (suite.status !== 'enabled') continue;
    const suiteLabel = suiteDisplayName(suite, locale);
    const options: SuiteCommandOption[] = [];
    for (const command of suite.manifest_snapshot?.commands ?? []) {
      if (!command.name) continue;
      const key = suiteCommandKey(suite, command);
      if (seen.has(key)) continue;
      const label = (isEnglish && command.display_en) || command.display || command.name;
      const description = (isEnglish && command.description_en) || command.description || command.summary || '';
      const searchText = [
        suite.name,
        suite.display,
        suite.manifest_snapshot?.display,
        suite.manifest_snapshot?.display_en,
        command.name,
        command.display,
        command.display_en,
        ...(command.aliases ?? []),
        command.description,
        command.description_en,
        command.summary,
      ]
        .filter(Boolean)
        .join(' ')
        .toLocaleLowerCase();
      if (terms.every(term => searchText.includes(term))) {
        seen.add(key);
        options.push({ key, suite, command, suiteLabel, label, description });
      }
    }
    if (options.length) groups.push({ suite, label: suiteLabel, options });
  }

  return groups;
}
