import type { SuiteCommand } from '@/types/suite';
import { describe, expect, it } from 'vitest';
import { suiteCommandFileHint, suiteCommandPrompt, validateSuiteCommandFiles } from './suite-command-inputs';

const readReport: SuiteCommand = {
  name: '/读年报',
  prefill: '请分析这份年报的经营表现。',
  input_files: { min: 1, max: 1, types: ['application/pdf'] },
};
const compareReports: SuiteCommand = {
  name: '/财报对比',
  input_files: { min: 2, max: 5, types: ['application/pdf'] },
};
const pdf = { name: 'annual.pdf', media_type: 'application/pdf' };

describe('suite command materials', () => {
  it('requires exactly one PDF to start reading a new annual report', () => {
    expect(validateSuiteCommandFiles(readReport, [])).toBe('missing_files');
    expect(validateSuiteCommandFiles(readReport, [pdf])).toBeNull();
    expect(validateSuiteCommandFiles(readReport, [pdf, pdf])).toBe('too_many_files');
  });

  it('requires two to five PDFs for a new comparison and honors the server metadata', () => {
    expect(validateSuiteCommandFiles(compareReports, [pdf])).toBe('missing_files');
    expect(validateSuiteCommandFiles(compareReports, [pdf, pdf])).toBeNull();
    expect(validateSuiteCommandFiles(compareReports, Array(5).fill(pdf))).toBeNull();
    expect(validateSuiteCommandFiles(compareReports, Array(6).fill(pdf))).toBe('too_many_files');
    expect(suiteCommandFileHint(compareReports)).toBe('上传 2–5 份 PDF 文件');
  });

  it('rejects unrelated file types and supports browsers without PDF MIME metadata', () => {
    expect(validateSuiteCommandFiles(readReport, [{ name: 'data.csv', type: 'text/csv' }])).toBe(
      'unsupported_file_type',
    );
    expect(validateSuiteCommandFiles(readReport, [{ name: 'annual.pdf', type: 'image/png' }])).toBe(
      'unsupported_file_type',
    );
    expect(validateSuiteCommandFiles(readReport, [{ name: 'ANNUAL.PDF', type: '' }])).toBeNull();
    expect(
      validateSuiteCommandFiles(readReport, [{ name: 'annual.pdf', media_type: 'application/octet-stream' }]),
    ).toBeNull();
  });

  it('requires files for explicit new analyses while ordinary follow-ups need no command', () => {
    expect(validateSuiteCommandFiles(readReport, [])).toBe('missing_files');
    expect(validateSuiteCommandFiles(compareReports, [])).toBe('missing_files');
    expect(validateSuiteCommandFiles(undefined, [])).toBeNull();
  });

  it('leaves commands without file requirements unchanged', () => {
    expect(validateSuiteCommandFiles({ name: '/查询' }, [])).toBeNull();
    expect(suiteCommandFileHint(undefined)).toBe('');
  });
});

describe('suite command prompt', () => {
  it('prefills a selected command without leaking an unrelated previous draft', () => {
    expect(suiteCommandPrompt(readReport, '/读')).toBe(readReport.prefill);
    expect(suiteCommandPrompt(readReport, '查询生产数据库')).toBe(readReport.prefill);
  });

  it('retains arguments when selecting a command while editing its slash token', () => {
    expect(suiteCommandPrompt(readReport, '/annual 只分析现金流')).toBe('只分析现金流');
  });
});
