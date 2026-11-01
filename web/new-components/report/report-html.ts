/** Repair serialization errors in old reports before sanitization or DOM parsing. */
export const normalizeReportHtml = (html: string): string => {
  // Old placeholder reports stringified {text: ...} nodes. Work on visible
  // text only: evidence attributes and literal code examples must stay intact.
  let proseQuote = '';
  html = html.replace(
    /<!--.*?-->|<(script|style|textarea|title|pre|code)\b(?:[^>"']|"[^"]*"|'[^']*')*>.*?<\/\1\s*>|<[^>"']*(?:"[^"]*"|'[^']*')[^>]*>|<[^>]*>|[^<]+/gis,
    (token: string) => {
      if (token.startsWith('<')) return token;
      return token.replace(
        /\{\s*(['"])text\1\s*:\s*(['"])|(['"])\s*\}/g,
        (match, keyQuote, openingQuote, closingQuote) => {
          if (openingQuote && !proseQuote) {
            proseQuote = openingQuote;
            return '';
          }
          if (closingQuote && closingQuote === proseQuote) {
            proseQuote = '';
            return '';
          }
          return match;
        },
      );
    },
  );
  const attributes = /\s[\w:.-]+\s*=\s*(?:\\(["'])(.*?)\\\1(?=\s|\/?>)|"[^"]*"|'[^']*'|[^\s>]+)/gs;
  const normalizeAttributes = (tag: string) =>
    tag.replace(attributes, (attribute: string, quote?: string, value?: string) => {
      if (!quote || value === undefined) return attribute;
      const prefix = attribute.slice(0, attribute.indexOf('\\'));
      const decoded = value.replace(/\\(["'])/g, '$1');
      const body = decoded.split(quote).join(quote === '"' ? '&quot;' : '&#39;');
      return `${prefix}${quote}${body}${quote}`;
    });
  // Leave comments and raw text intact, including JavaScript, CSS and quoted
  // HTML examples. Valid quoted attributes are consumed whole so JSON selector
  // escapes inside them cannot be mistaken for attribute delimiters.
  return html.replace(
    /<!--.*?-->|<(script|style|textarea|title)\b(?:[^>"']|"[^"]*"|'[^']*')*>.*?<\/\1\s*>|<[a-zA-Z][\w:-]*\b(?:[^>"']|"[^"]*"|'[^']*')*>|(?<=>)"\s*\+\s*"(?=<)/gis,
    (token: string, rawTag?: string) => {
      if (!token.startsWith('<')) return '';
      if (token.startsWith('<!--')) return token;
      if (!rawTag) return normalizeAttributes(token);
      const opening = token.match(/^<[a-zA-Z][\w:-]*\b(?:[^>"']|"[^"]*"|'[^']*')*>/)![0];
      return normalizeAttributes(opening) + token.slice(opening.length);
    },
  );
};
