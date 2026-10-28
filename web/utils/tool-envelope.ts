/**
 * DB-GPT tool-result envelope helpers.
 *
 * Harness-engine tools (pi bridge) return their result as a JSON envelope
 * string — ``{"chunks": [{"output_type": ..., "content": ...}]}`` — inside
 * plain ``text`` step outputs. These helpers scan such envelopes out of
 * arbitrary streamed text (string-aware brace matching, multiple envelopes
 * per string, non-envelope residue preserved) so the UI can render readable
 * markdown and promote embedded html/image payloads to first-class
 * artifacts instead of leaking raw JSON.
 */

/** Index just past the balanced ``{...}`` object starting at ``start``. */
function matchBalancedObject(text: string, start: number): number {
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < text.length; i++) {
    const ch = text[i];
    if (inStr) {
      if (esc) esc = false;
      else if (ch === '\\') esc = true;
      else if (ch === '"') inStr = false;
      continue;
    }
    if (ch === '"') inStr = true;
    else if (ch === '{') depth++;
    else if (ch === '}') {
      depth--;
      if (depth === 0) return i + 1;
    }
  }
  return -1;
}

const ENVELOPE_MARKERS = ['{"chunks"', '{ "chunks"'];

/** Fallback: pull ``"output_type": X, "content": "..."`` pairs by regex when
 *  balanced-object JSON.parse fails (truncated / concatenated envelopes). */
const CHUNK_PAIR_RE = /"output_type"\s*:\s*"(markdown|text|html|image)"\s*,\s*"content"\s*:\s*"((?:[^"\\]|\\.)*)"/g;
const CHUNK_PAIR_RE_REV = /"content"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"output_type"\s*:\s*"(markdown|text|html|image)"/g;

function unescapeJsonString(raw: string): string | null {
  try {
    const v = JSON.parse(`"${raw}"`);
    return typeof v === 'string' ? v : null;
  } catch {
    // Truncated envelope: best-effort manual unescape.
    return raw.replace(/\\n/g, '\n').replace(/\\t/g, '\t').replace(/\\"/g, '"').replace(/\\\\/g, '\\');
  }
}

/** Unclosed-content variant for truncated envelopes (history caps). */
const CHUNK_OPEN_RE = /"output_type"\s*:\s*"(markdown|text)"\s*,\s*"content"\s*:\s*"((?:[^"\\]|\\.)*)/g;

function regexChunkContents(text: string): { type: string; content: string }[] {
  const found: { type: string; content: string }[] = [];
  for (const re of [CHUNK_PAIR_RE, CHUNK_PAIR_RE_REV]) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      const type = re === CHUNK_PAIR_RE ? m[1] : m[2];
      const rawContent = re === CHUNK_PAIR_RE ? m[2] : m[1];
      const content = unescapeJsonString(rawContent);
      if (content != null && content.trim()) found.push({ type, content });
    }
    if (found.length) break;
  }
  if (!found.length) {
    CHUNK_OPEN_RE.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = CHUNK_OPEN_RE.exec(text)) !== null) {
      const content = unescapeJsonString(m[2]);
      if (content != null && content.trim()) found.push({ type: m[1], content });
    }
  }
  return found;
}

function nextEnvelopeStart(text: string, from: number): number {
  let best = -1;
  // Tool envelopes may put success/artifact_id before chunks. Match their
  // complete object instead of depending on JSON property order.
  const candidate = text.indexOf('{', from);
  if (candidate !== -1) {
    const end = matchBalancedObject(text, candidate);
    if (end !== -1) {
      try {
        if (Array.isArray(JSON.parse(text.slice(candidate, end))?.chunks)) best = candidate;
      } catch {
        /* continue with the streaming/truncated envelope markers */
      }
    }
  }
  for (const marker of ENVELOPE_MARKERS) {
    const idx = text.indexOf(marker, from);
    if (idx !== -1 && (best === -1 || idx < best)) best = idx;
  }
  return best;
}

/** Parse every ``{"chunks": [...]}`` envelope embedded in ``text``. */
export function extractEnvelopeObjects(text: string): any[] {
  const envelopes: any[] = [];
  let cursor = 0;
  let start = nextEnvelopeStart(text, cursor);
  while (start !== -1) {
    const end = matchBalancedObject(text, start);
    if (end === -1) break;
    try {
      const parsed = JSON.parse(text.slice(start, end));
      if (parsed && Array.isArray(parsed.chunks)) envelopes.push(parsed);
    } catch {
      /* malformed envelope: skip */
    }
    cursor = end;
    start = nextEnvelopeStart(text, cursor);
  }
  return envelopes;
}

/** Readable markdown/text payload of all envelopes + non-envelope residue. */
export function envelopeReadableText(text: string): string | null {
  if (!text || !text.includes('"chunks"')) return null;
  const parts: string[] = [];
  let cursor = 0;
  let start = nextEnvelopeStart(text, cursor);
  while (start !== -1) {
    const residue = text.slice(cursor, start).trim();
    if (residue) parts.push(residue);
    const end = matchBalancedObject(text, start);
    if (end === -1) {
      // Truncated envelope (history caps): salvage readable chunks by
      // regex instead of leaking the raw payload as tail text.
      for (const chunk of regexChunkContents(text.slice(start))) {
        if ((chunk.type === 'markdown' || chunk.type === 'text') && chunk.content.trim()) {
          parts.push(chunk.content);
        }
      }
      cursor = text.length;
      break;
    }
    try {
      const parsed = JSON.parse(text.slice(start, end));
      for (const chunk of parsed?.chunks || []) {
        if (!chunk || typeof chunk !== 'object') continue;
        const type = chunk.output_type;
        if ((type === 'markdown' || type === 'text') && typeof chunk.content === 'string' && chunk.content.trim()) {
          parts.push(chunk.content);
        }
      }
    } catch {
      /* skip */
    }
    cursor = end;
    start = nextEnvelopeStart(text, cursor);
  }
  const tail = text.slice(cursor).trim();
  if (tail) parts.push(tail);
  if (!parts.length && text.includes('"chunks"')) {
    // Balanced parsing found nothing usable — regex fallback.
    for (const chunk of regexChunkContents(text)) {
      if ((chunk.type === 'markdown' || chunk.type === 'text') && chunk.content.trim()) {
        parts.push(chunk.content);
      }
    }
  }
  return parts.length ? parts.join('\n\n') : null;
}

/** html/image payloads embedded in envelopes, as synthetic outputs. */
export function envelopeEmbeddedOutputs(text: string): { type: 'html' | 'image' | 'expert_suite'; content: any }[] {
  const found: { type: 'html' | 'image' | 'expert_suite'; content: any }[] = [];
  for (const envelope of extractEnvelopeObjects(text)) {
    for (const chunk of envelope.chunks || []) {
      if (!chunk || typeof chunk !== 'object') continue;
      if (chunk.output_type === 'html' && (typeof chunk.content === 'string' || chunk.content)) {
        found.push({
          type: 'html',
          content: {
            content: typeof chunk.content === 'string' ? chunk.content : String(chunk.content),
            title: chunk.title || envelope.title || 'Report',
          },
        });
      } else if (chunk.output_type === 'image' && chunk.content != null) {
        found.push({ type: 'image', content: chunk.content });
      } else if (chunk.output_type === 'expert_suite' && chunk.content?.artifact_id) {
        found.push({ type: 'expert_suite', content: chunk.content });
      }
    }
  }
  if (!found.length && text.includes('"chunks"')) {
    for (const chunk of regexChunkContents(text)) {
      if (chunk.type === 'html' && chunk.content.trim()) {
        found.push({ type: 'html', content: { content: chunk.content, title: 'Report' } });
      } else if (chunk.type === 'image' && chunk.content.trim()) {
        found.push({ type: 'image', content: chunk.content });
      }
    }
  }
  return found;
}
