/**
 * Wiki markdown renderer: markdown-it + [[slug|alias]] wiki-link support.
 * Renders wiki links as internal anchors handled via click delegation.
 */
import { WikiPageType } from '@/types/wiki';
import { Tag } from 'antd';
import MarkdownIt from 'markdown-it';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

const md: MarkdownIt = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: false,
});

export const WIKI_LINK_RE = /\[\[([^\]|#]+)(?:\|([^\]|#]*))?\]\]/g;

/** Convert [[slug|alias]] into plain anchors with a wikilink:// scheme. */
export const preprocessWikiLinks = (content: string) =>
  (content || '').replace(WIKI_LINK_RE, (_match, slug: string, alias?: string) => {
    const display = (alias || '').trim() || slug.split('/').pop() || slug;
    return `[${display}](wikilink://${encodeURIComponent(slug.trim())})`;
  });

export const PAGE_TYPE_COLORS: Record<WikiPageType, string> = {
  summary: '#4da3ff',
  entity: '#34d399',
  concept: '#f5a623',
  synthesis: '#a78bfa',
  comparison: '#f87171',
  index: '#8e8b8b',
};

export function WikiPageTypeTag({ type }: { type: WikiPageType }) {
  const { t } = useTranslation();
  return <Tag color={PAGE_TYPE_COLORS[type] || '#8e8b8b'}>{t(`wiki_type_${type}`, type)}</Tag>;
}

export default function WikiMarkdown({
  content,
  onLinkClick,
  className,
}: {
  content: string;
  onLinkClick: (slug: string) => void;
  className?: string;
}) {
  const html = useMemo(() => md.render(preprocessWikiLinks(content || '')), [content]);

  const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    const anchor = target.closest('a');
    if (!anchor) return;
    const href = anchor.getAttribute('href') || '';
    if (href.startsWith('wikilink://')) {
      event.preventDefault();
      const slug = decodeURIComponent(href.slice('wikilink://'.length));
      onLinkClick(slug);
    } else if (href.startsWith('http')) {
      event.preventDefault();
      window.open(href, '_blank');
    }
  };

  return (
    <div
      className={`wiki-markdown ${className || ''} text-sm text-gray-700 dark:text-gray-300 leading-relaxed [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:mb-2 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:mt-5 [&_h2]:mb-2 [&_h2]:border-b [&_h2]:border-gray-200 dark:[&_h2]:border-gray-700 [&_h3]:text-sm [&_h3]:font-semibold [&_h2]:dark:text-gray-200 [&_h1]:dark:text-gray-200 [&_h3]:dark:text-gray-200 [&_table]:my-3 [&_th]:border [&_th]:border-gray-300 dark:[&_th]:border-gray-600 [&_th]:px-3 [&_th]:py-1.5 [&_th]:bg-gray-100 dark:[&_th]:bg-gray-800 [&_td]:border [&_td]:border-gray-300 dark:[&_td]:border-gray-600 [&_td]:px-3 [&_td]:py-1.5 [&_ol]:pl-5 [&_ul]:pl-5 [&_li]:my-1 [&_a]:text-[#4da3ff] [&_a]:border-b [&_a]:border-dashed [&_a]:border-[#4da3ff]/50 [&_a]:cursor-pointer`}
      onClick={handleClick}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
