import React from 'react';
import { offlineCitationLabels } from '../../../web/new-components/financial-analysis/offline-citations';
// Render report text without the app's network-capable rich-artifact renderer.
function inline(text: string) {
  // Offline reports retain readable evidence labels without pretending that
  // authenticated, revision-pinned application links work outside the app.
  text = offlineCitationLabels(text);
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => part.startsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong> : part);
}
export default function Markdown({ children }: { children: string }) {
  return <>{children.split('\n\n').map((block, index) => block.startsWith('- ') ? <ul key={index} className='my-3 list-disc pl-5 space-y-1'>{block.split('\n').map((line, item) => <li key={item}>{inline(line.replace(/^- /, ''))}</li>)}</ul> : <p key={index} className='my-2'>{inline(block)}</p>)}</>;
}
