import React from 'react';
import Mermaid from '@theme/Mermaid';

export function ConfigDiagram({ relationships }) {
  const diagram = `
graph TD
${relationships.map(r => `    ${r.from} -->|${r.label}| ${r.to}`).join('\n')}
  `.trim();

  return <Mermaid value={diagram} />;
}