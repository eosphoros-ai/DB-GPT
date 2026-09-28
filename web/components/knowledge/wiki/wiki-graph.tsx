/**
 * Wiki link graph: lightweight force-directed SVG renderer.
 * Simulation parameters ported from WeKnora (alpha decay, repulsion,
 * edge spring, centering gravity). React only handles lifecycle/data;
 * rendering is imperative via SVG DOM.
 */
import { apiInterceptors, getWikiGraph, getWikiPage, searchWikiPages } from '@/client/api';
import { WikiGraphEdge, WikiGraphNode, WikiGraphResult, WikiPageType } from '@/types/wiki';
import { ApartmentOutlined, ReloadOutlined } from '@ant-design/icons';
import { Badge, Button, Empty, Segmented, Select, Spin } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { PAGE_TYPE_COLORS, WikiPageTypeTag } from './wiki-markdown';

const GRAPH_EGO_LIMIT = 500;

interface GNode extends WikiGraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  pinned: boolean;
}

interface WikiGraphProps {
  spaceId: string | number;
}

export default function WikiGraph({ spaceId }: WikiGraphProps) {
  const { t } = useTranslation();
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);
  const nodesRef = useRef<GNode[]>([]);
  const simRef = useRef<number | null>(null);
  const viewRef = useRef({ x: 0, y: 0, k: 1 });

  const [mode, setMode] = useState<'overview' | 'ego'>('overview');
  const [center, setCenter] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [graph, setGraph] = useState<WikiGraphResult | null>(null);
  const [searchValue, setSearchValue] = useState<string>('');
  const [searchOptions, setSearchOptions] = useState<{ slug: string; title: string; page_type: WikiPageType }[]>([]);
  const [highlight, setHighlight] = useState<string | null>(null);
  const [selected, setSelected] = useState<WikiGraphNode | null>(null);

  const applyGraph = (data: WikiGraphResult, keepLayout: boolean) => {
    const previous = new Map(nodesRef.current.map(n => [n.slug, n]));
    const width = canvasRef.current?.clientWidth || 800;
    const height = canvasRef.current?.clientHeight || 600;
    const seedRadius = Math.min(width, height) * 0.35;
    const next: GNode[] = data.nodes.map((node, index) => {
      const old = keepLayout ? previous.get(node.slug) : undefined;
      if (old) return { ...node, x: old.x, y: old.y, vx: 0, vy: 0, pinned: old.pinned };
      const angle = (index / Math.max(1, data.nodes.length)) * Math.PI * 2;
      const jitter = seedRadius * (0.3 + ((index * 7919) % 50) / 100);
      return {
        ...node,
        x: width / 2 + Math.cos(angle) * jitter,
        y: height / 2 + Math.sin(angle) * jitter,
        vx: 0,
        vy: 0,
        pinned: false,
      };
    });
    nodesRef.current = next;
    setGraph({
      ...data,
      edges: data.edges.filter(e => next.some(n => n.slug === e.source) && next.some(n => n.slug === e.target)),
      nodes: next,
    });
    startSimulation();
  };

  const startSimulation = () => {
    let alpha = 1;
    if (simRef.current) window.clearInterval(simRef.current);
    simRef.current = window.setInterval(() => {
      const nodes = nodesRef.current;
      if (!nodes.length || alpha < 0.005) {
        if (simRef.current) window.clearInterval(simRef.current);
        simRef.current = null;
        return;
      }
      const width = canvasRef.current?.clientWidth || 800;
      const height = canvasRef.current?.clientHeight || 600;
      const slugIndex = new Map(nodes.map((n, i) => [n.slug, i]));
      const edges = graphRef.current?.edges || [];
      // repulsion (sampled to keep O(n^1.5) in P0)
      for (let i = 0; i < nodes.length; i++) {
        const a = nodes[i];
        for (let j = i + 1; j < nodes.length; j++) {
          const b = nodes[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist2 = dx * dx + dy * dy || 1;
          if (dist2 > 90000) continue; // 300px cutoff
          const force = (1500 * alpha) / dist2;
          const d = Math.sqrt(dist2);
          const fx = (dx / d) * force;
          const fy = (dy / d) * force;
          a.vx -= fx;
          a.vy -= fy;
          b.vx += fx;
          b.vy += fy;
        }
      }
      // edge springs
      for (const edge of edges) {
        const ai = slugIndex.get(edge.source);
        const bi = slugIndex.get(edge.target);
        if (ai === undefined || bi === undefined) continue;
        const a = nodes[ai];
        const b = nodes[bi];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (dist - 120) * 0.005 * alpha;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx += fx;
        a.vy += fy;
        b.vx -= fx;
        b.vy -= fy;
      }
      // gravity + integrate
      for (const node of nodes) {
        node.vx += (width / 2 - node.x) * 0.002 * alpha;
        node.vy += (height / 2 - node.y) * 0.002 * alpha;
        node.vx *= 0.85;
        node.vy *= 0.85;
        if (!node.pinned) {
          node.x += node.vx;
          node.y += node.vy;
        }
      }
      alpha *= 0.985;
      render();
    }, 30);
  };

  // keep latest graph object for the sim loop
  const graphRef = useRef<WikiGraphResult | null>(null);
  useEffect(() => {
    graphRef.current = graph;
  }, [graph]);

  const render = () => {
    const svg = svgRef.current;
    if (!svg) return;
    const nodes = nodesRef.current;
    const edges = (graphRef.current?.edges || []).filter(
      e => nodes.some(n => n.slug === e.source) && nodes.some(n => n.slug === e.target),
    );
    svg.setAttribute('data-nodes', String(nodes.length));
    renderFn.current?.(svg, nodes, edges);
  };

  const renderFn = useRef<((svg: SVGSVGElement, nodes: GNode[], edges: WikiGraphEdge[]) => void) | null>(null);

  const load = async (loadMode: 'overview' | 'ego', centerSlug?: string, depth = 1) => {
    setLoading(true);
    const [, data] = await apiInterceptors(
      getWikiGraph(spaceId, {
        mode: loadMode,
        center: centerSlug,
        depth,
        limit: GRAPH_EGO_LIMIT,
      }),
    );
    setLoading(false);
    if (data) {
      applyGraph(data, loadMode === 'ego');
    }
  };

  useEffect(() => {
    if (!spaceId) return;
    // seed renderer once canvas is ready
    renderFn.current = (svg, nodes, edges) => {
      const view = viewRef.current;
      let html = `<g transform="translate(${view.x},${view.y}) scale(${view.k})">`;
      for (const e of edges) {
        const a = nodes.find(n => n.slug === e.source);
        const b = nodes.find(n => n.slug === e.target);
        if (!a || !b) continue;
        const isHighlight = highlight && (e.source === highlight || e.target === highlight);
        html += `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${isHighlight ? '#f5a623' : '#343030'}" stroke-width="${isHighlight ? 1.6 : 1}"/>`;
      }
      for (const n of nodes) {
        const color = PAGE_TYPE_COLORS[n.page_type] || '#8e8b8b';
        const r = 6 + Math.min(10, n.link_count);
        const isHi = highlight === n.slug || highlight === null;
        const labelOpacity = view.k > 0.7 || n.link_count > 2 ? 1 : 0;
        html += `<g class="gnode" data-slug="${n.slug}" style="opacity:${isHi ? 1 : 0.25}">`;
        html += `<circle cx="${n.x}" cy="${n.y}" r="${r}" fill="${color}" fill-opacity="0.85" stroke="${highlight === n.slug ? '#f5a623' : 'none'}" stroke-width="2"/>`;
        html += `<text x="${n.x + r + 3}" y="${n.y + 4}" font-size="11" fill="${labelOpacity ? '#b7b1b1' : 'transparent'}">${escapeHtml(n.title)}</text>`;
        html += `</g>`;
      }
      html += `</g>`;
      svg.innerHTML = html;
    };
    if (mode === 'overview') load('overview');
    return () => {
      if (simRef.current) window.clearInterval(simRef.current);
      simRef.current = null;
    };
  }, [spaceId]); // eslint-disable-line react-hooks/exhaustive-deps

  // click handling (event delegation on svg)
  const handleSvgClick = (event: React.MouseEvent<SVGSVGElement>) => {
    const target = event.target as SVGElement;
    const group = target.closest('g.gnode') as SVGGElement | null;
    if (!group) {
      setHighlight(null);
      return;
    }
    const slug = group.getAttribute('data-slug');
    if (!slug) return;
    setHighlight(slug);
    const node = nodesRef.current.find(n => n.slug === slug);
    setSelected(node || null);
  };

  // double click: switch ego center
  const handleSvgDoubleClick = (event: React.MouseEvent<SVGSVGElement>) => {
    const target = event.target as SVGElement;
    const group = target.closest('g.gnode') as SVGGElement | null;
    if (!group) return;
    const slug = group.getAttribute('data-slug');
    if (!slug) return;
    setCenter(slug);
    setMode('ego');
    load('ego', slug, 1);
  };

  // pan / zoom
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    const onDown = (e: MouseEvent) => {
      dragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
    };
    const onMove = (e: MouseEvent) => {
      if (!dragging) return;
      viewRef.current.x += e.clientX - lastX;
      viewRef.current.y += e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;
    };
    const onUp = () => {
      dragging = false;
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const view = viewRef.current;
      const scale = e.deltaY > 0 ? 0.9 : 1.1;
      view.k = Math.max(0.2, Math.min(3, view.k * scale));
    };
    svg.addEventListener('mousedown', onDown);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    svg.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      svg.removeEventListener('mousedown', onDown);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      svg.removeEventListener('wheel', onWheel);
    };
  }, []);

  // entity click → preview page (fetch lite content)
  const [preview, setPreview] = useState<{ title: string; content: string } | null>(null);
  useEffect(() => {
    if (!selected) {
      setPreview(null);
      return;
    }
    (async () => {
      const [, data] = await apiInterceptors(getWikiPage(spaceId, selected.slug));
      setPreview(data ? { title: data.title, content: data.content } : null);
    })();
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = async (value: string) => {
    setSearchValue(value);
    if (!value || value.length < 1) {
      setSearchOptions([]);
      return;
    }
    const [, data] = await apiInterceptors(searchWikiPages(spaceId, value, 8));
    setSearchOptions((data?.results || []).map(r => ({ slug: r.slug, title: r.title, page_type: r.page_type })));
  };

  const legendTypes: WikiPageType[] = ['summary', 'entity', 'concept', 'synthesis', 'comparison'];
  const hasGraph = graph && graph.nodes.length > 0;

  return (
    <div ref={canvasRef} className='relative w-full h-full overflow-hidden bg-gray-50 dark:bg-[#131010]'>
      <svg
        ref={svgRef}
        className='w-full h-full cursor-move'
        onClick={handleSvgClick}
        onDoubleClick={handleSvgDoubleClick}
      />

      {/* toolbar */}
      <div className='absolute top-3 left-3 flex flex-col gap-2' style={{ width: 240 }}>
        <Select
          showSearch
          allowClear
          size='small'
          value={searchValue && searchOptions.find(o => o.slug === searchValue) ? searchValue : undefined}
          placeholder={t('wiki_graph_search_placeholder')}
          filterOption={false}
          onSearch={handleSearch}
          onChange={slug => {
            if (!slug) return;
            setCenter(slug);
            setMode('ego');
            load('ego', slug, 1);
          }}
          options={searchOptions.map(o => ({ value: o.slug, label: o.title }))}
        />
        <div className='flex gap-1.5'>
          <Segmented
            size='small'
            value={mode}
            onChange={value => {
              const next = value as 'overview' | 'ego';
              setMode(next);
              if (next === 'overview') load('overview');
              else if (center) load('ego', center, 1);
            }}
            options={[
              { label: t('wiki_graph_overview'), value: 'overview' },
              { label: t('wiki_graph_ego'), value: 'ego' },
            ]}
          />
          <Button
            size='small'
            icon={<ApartmentOutlined />}
            onClick={() => center && load('ego', center, center && mode === 'ego' ? 2 : 1)}
          >
            {t('wiki_graph_expand')}
          </Button>
        </div>
        <Button
          size='small'
          icon={<ReloadOutlined />}
          onClick={() => load(mode, center || undefined, 1)}
          className='w-fit'
        >
          {t('reload')}
        </Button>
      </div>

      {/* legend */}
      <div className='absolute top-3 right-3 bg-white dark:bg-[#1b1818] border dark:border-gray-700 rounded-lg px-3 py-2 shadow-md'>
        <div className='text-xs text-gray-400 mb-1.5'>{t('wiki_graph_legend')}</div>
        {legendTypes.map(type => (
          <div key={type} className='flex items-center gap-2 text-xs text-gray-500 dark:text-gray-300 py-0.5'>
            <span className='w-2.5 h-2.5 rounded-full inline-block' style={{ background: PAGE_TYPE_COLORS[type] }} />
            {t(`wiki_type_${type}`)}
          </div>
        ))}
        {graph && (
          <div className='text-xs text-gray-400 mt-1.5 border-t dark:border-gray-700 pt-1.5'>
            {t('wiki_graph_stats', { shown: graph.nodes.length, total: graph.meta.total })}
          </div>
        )}
      </div>

      {/* page preview drawer */}
      {selected && (
        <div className='absolute top-0 right-0 bottom-0 w-[380px] bg-white dark:bg-[#1b1818] border-l dark:border-gray-700 shadow-xl overflow-auto p-4'>
          <div className='flex items-center gap-2 mb-2'>
            <WikiPageTypeTag type={selected.page_type} />
            <span className='ml-auto text-xs text-gray-400'>{t('wiki_node_links', { n: selected.link_count })}</span>
          </div>
          <div className='text-lg font-bold text-gray-900 dark:text-gray-100 mb-3'>{selected.title}</div>
          <p className='text-xs text-gray-400 mb-2'>{t('wiki_graph_center_hint')}</p>
          {preview ? (
            <div className='text-sm text-gray-600 dark:text-gray-300 whitespace-pre-wrap'>
              {preview.content.slice(0, 500)}
            </div>
          ) : (
            <Spin size='small' />
          )}
        </div>
      )}

      {/* empty / loading */}
      {loading && (
        <div className='absolute inset-0 flex items-center justify-center pointer-events-none'>
          <Spin size='large' />
        </div>
      )}
      {!loading && !hasGraph && (
        <div className='absolute inset-0 flex items-center justify-center'>
          <Empty description={t('wiki_empty_no_pages')} />
        </div>
      )}
      {graph?.meta.truncated && (
        <div className='absolute bottom-3 left-3 text-xs text-gray-400 bg-white dark:bg-[#1b1818] border dark:border-gray-700 rounded px-2 py-1'>
          <Badge status='warning' text={t('wiki_graph_truncated')} />
        </div>
      )}
    </div>
  );
}

function escapeHtml(text: string | undefined) {
  return (text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
