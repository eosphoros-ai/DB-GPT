/** Display only source coordinates that were captured by the knowledge tools. */
export function referenceLocation(locator: Record<string, unknown> = {}): string {
  const parts: string[] = [];
  if (typeof locator.path === 'string' && locator.path) parts.push(locator.path);
  if (locator.document_id !== undefined && locator.document_id !== null)
    parts.push(`文档 ${String(locator.document_id)}`);
  if (locator.page !== undefined && locator.page !== null) parts.push(`第 ${String(locator.page)} 页`);
  if (typeof locator.chunk_id === 'string' && locator.chunk_id) {
    const index = locator.chunk_index;
    if (typeof index === 'number' && Number.isInteger(index) && index >= 0) parts.push(`第 ${index + 1} 个切片`);
    parts.push(`切片 ID：${locator.chunk_id}`);
  }
  const matchedLines = Array.isArray(locator.matched_lines)
    ? locator.matched_lines.filter((line): line is number => typeof line === 'number')
    : [];
  if (matchedLines.length)
    parts.push(`${locator.line_scope === 'chunk' ? '切片内命中行' : '命中行'} ${matchedLines.join(', ')}`);
  else if (typeof locator.start_line === 'number' && typeof locator.end_line === 'number') {
    parts.push(`第 ${locator.start_line}-${locator.end_line} 行`);
  } else if (typeof locator.read_start_line === 'number' && typeof locator.read_end_line === 'number') {
    parts.push(`本次读取第 ${locator.read_start_line}-${locator.read_end_line} 行`);
  }
  return parts.join(' · ') || '未记录具体来源位置';
}
