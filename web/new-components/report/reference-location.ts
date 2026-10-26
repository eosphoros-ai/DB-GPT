import { reportText } from './report-i18n';

/** Display only source coordinates that were captured by the knowledge tools. */
export function referenceLocation(locator: Record<string, unknown> = {}): string {
  const parts: string[] = [];
  if (typeof locator.path === 'string' && locator.path) parts.push(locator.path);
  if (locator.document_id !== undefined && locator.document_id !== null)
    parts.push(reportText('evidence_location_document', { id: String(locator.document_id) }));
  if (locator.page !== undefined && locator.page !== null)
    parts.push(reportText('evidence_location_page', { page: String(locator.page) }));
  if (typeof locator.chunk_id === 'string' && locator.chunk_id) {
    const index = locator.chunk_index;
    if (typeof index === 'number' && Number.isInteger(index) && index >= 0)
      parts.push(reportText('evidence_location_chunk_index', { index: index + 1 }));
    parts.push(reportText('evidence_location_chunk_id', { id: locator.chunk_id }));
  }
  const matchedLines = Array.isArray(locator.matched_lines)
    ? locator.matched_lines.filter((line): line is number => typeof line === 'number')
    : [];
  if (matchedLines.length)
    parts.push(
      `${locator.line_scope === 'chunk' ? reportText('evidence_location_matched_chunk') : reportText('evidence_location_matched')} ${matchedLines.join(', ')}`,
    );
  else if (typeof locator.start_line === 'number' && typeof locator.end_line === 'number') {
    parts.push(reportText('evidence_location_lines', { start: locator.start_line, end: locator.end_line }));
  } else if (typeof locator.read_start_line === 'number' && typeof locator.read_end_line === 'number') {
    parts.push(
      reportText('evidence_location_read_lines', {
        start: locator.read_start_line,
        end: locator.read_end_line,
      }),
    );
  }
  return parts.join(' · ') || reportText('evidence_location_unknown');
}
