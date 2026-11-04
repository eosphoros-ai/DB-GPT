import type { SuiteCommand } from '@/types/suite';

export interface SuiteInputFile {
  name: string;
  media_type?: string;
  type?: string;
}

export type SuiteInputProblem = 'missing_files' | 'too_many_files' | 'unsupported_file_type';

/** Validate the materials selected for this send, never unrelated files from history. */
export function validateSuiteCommandFiles(
  command: SuiteCommand | undefined,
  files: readonly SuiteInputFile[],
  hasMatchingReport = false,
): SuiteInputProblem | null {
  const rules = command?.input_files;
  if (!rules) return null;
  if (files.length === 0 && hasMatchingReport) return null;
  if (files.length < rules.min) return 'missing_files';
  if (files.length > rules.max) return 'too_many_files';
  if (
    files.some(file => {
      const type = (file.media_type || file.type || '').toLowerCase().split(';')[0].trim();
      if (rules.types.includes(type)) return false;
      // Some browsers leave PDF MIME empty; the server still checks the actual bytes.
      return !(
        (!type || type === 'application/octet-stream') &&
        rules.types.includes('application/pdf') &&
        file.name.toLowerCase().endsWith('.pdf')
      );
    })
  ) {
    return 'unsupported_file_type';
  }
  return null;
}

export function suiteCommandFileHint(command: SuiteCommand | undefined, locale = 'zh'): string {
  const rules = command?.input_files;
  if (!rules) return '';
  const count = rules.min === rules.max ? `${rules.min}` : `${rules.min}–${rules.max}`;
  const formats = rules.types.map(type => (type === 'application/pdf' ? 'PDF' : type)).join(' / ');
  return locale.toLowerCase().startsWith('en')
    ? `Upload ${count} ${formats} file${rules.max === 1 ? '' : 's'}`
    : `上传 ${count} 份 ${formats} 文件`;
}

export function suiteCommandFileError(problem: SuiteInputProblem, command: SuiteCommand, locale = 'zh'): string {
  const hint = suiteCommandFileHint(command, locale);
  const isEnglish = locale.toLowerCase().startsWith('en');
  if (problem === 'unsupported_file_type') {
    return isEnglish ? `Unsupported file type. ${hint}.` : `附件格式不支持，请${hint}。`;
  }
  if (problem === 'too_many_files') {
    return isEnglish ? `Too many files. ${hint}.` : `附件数量过多，请${hint}。`;
  }
  return isEnglish ? `${hint} before starting this task.` : `请先${hint}，再开始任务。`;
}

/** A document comparison cannot reuse a saved single-report result as its input. */
export function suiteCommandMatchesReportMode(command: SuiteCommand | undefined, mode?: 'report' | 'comparison') {
  if (!command?.input_files) return false;
  return (command.input_files.min > 1 ? 'comparison' : 'report') === (mode || 'report');
}

/** Preserve supplied command arguments; otherwise use the localized input guide. */
export function suiteCommandPrompt(command: SuiteCommand, input = ''): string {
  const argumentsText = /^\s*\/[^\s]+\s+([\s\S]*)$/.exec(input)?.[1]?.trim();
  return argumentsText || command.prefill || '';
}
