/** Application evidence links need authorization; keep their labels in snapshots. */
export function offlineCitationLabels(text: string) {
  return text.replace(
    /\[([^\]]+)\]\(#financial-report\/[a-f0-9-]{36}\/(?:fact|calculation)\/[A-Za-z0-9_-]+(?:\?revision=[A-Za-z0-9_-]+)?\)/gi,
    '$1',
  );
}
