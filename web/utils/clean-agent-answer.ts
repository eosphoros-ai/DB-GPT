/** Present a legacy terminate envelope as its answer, without exposing protocol text. */
export function cleanAgentAnswer(text: string): string {
  const termination = /^Action:\s*terminate\s*$/im.exec(text);
  if (termination) {
    const input = text.indexOf('Action Input:', termination.index);
    if (input >= 0) {
      try {
        const payload: unknown = JSON.parse(text.slice(input + 'Action Input:'.length).trim());
        if (payload && typeof payload === 'object' && 'output' in payload && typeof payload.output === 'string') {
          return payload.output.trim();
        }
      } catch {
        // Preserve the existing fallback for incomplete legacy streams.
      }
    }
  }
  return text
    .replace(/\\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/"\s*\}\s*$/, '')
    .replace(/^(Thought|Action|Action Input|Observation|Phase):\s*/gm, '')
    .trim();
}
