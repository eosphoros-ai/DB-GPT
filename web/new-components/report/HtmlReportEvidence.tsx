import { getRenderObservations, getStandaloneReportRun, saveRenderObservation } from '@/client/api/report/standalone';
import { AutoChart, BackEndChartType, getChartType } from '@/components/chart';
import type { BrowserRenderObservation, ReportArtifact, ReportRun } from '@/types/report';
import type { Datum } from '@antv/ava';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { format as formatSql } from 'sql-formatter';
import ReportIframe, { resolveReportAssetUrls, sanitizeEmbeddedReportHtml } from './ReportIframe';
import { artifactTitle } from './artifact-title';
import { referenceLocation as formatReferenceLocation } from './reference-location';
import { artifactSourceName, type KnowledgeSpaceNames } from './report-source';
import { useKnowledgeSpaceNames } from './use-knowledge-space-names';

type Props = {
  html: string;
  reportId: string;
  reportRunId: string;
  iframeRef?: React.RefObject<HTMLIFrameElement>;
  onArtifactFocus?: (stepId: string) => void;
};

type NativeChartSpec = { renderer?: string; type?: string; data?: unknown };
type NativeChartMount = { artifact: ReportArtifact; spec: NativeChartSpec; host: HTMLElement };
type ReportChartTypes = Parameters<typeof AutoChart>[0]['chartType'];

/**
 * Report-only compatibility for native protocols that DB-GPT's older
 * VisChart prompts can emit but its current frontend helper does not name.
 * Keep this mapping outside the shared AutoChart so stock chat behaviour is
 * unchanged.
 */
const reportChartTypes = (type: string | undefined): ReportChartTypes => {
  if (type === 'response_donut_chart') return ['donut_chart'] as ReportChartTypes;
  if (type === 'response_bubble_chart') return ['bubble_chart'] as ReportChartTypes;
  if (type === 'response_heatmap') return getChartType('response_heatmap_chart');
  return getChartType((type || 'response_table') as BackEndChartType);
};

const tabularRows = (artifact?: ReportArtifact): Datum[] => {
  const inline = artifact?.result?.inline;
  if (Array.isArray(inline) && inline.every(row => row && typeof row === 'object' && !Array.isArray(row)))
    return inline as Datum[];
  if (!inline || typeof inline !== 'object' || Array.isArray(inline)) return [];
  const tabular = inline as { columns?: unknown; rows?: unknown };
  if (!Array.isArray(tabular.columns) || !Array.isArray(tabular.rows)) return [];
  const columns = tabular.columns.filter((column): column is string => typeof column === 'string');
  return tabular.rows.flatMap(row => {
    if (Array.isArray(row)) return [Object.fromEntries(columns.map((column, index) => [column, row[index]])) as Datum];
    if (row && typeof row === 'object') return [row as Datum];
    return [];
  });
};

/**
 * DB-GPT's chart_query may return an ordinal grouping key as a number (for
 * example Walmart's Store 20). AVA then sees two numeric measures and cannot
 * form a column/pie encoding, leaving the native chart host blank. The query
 * result is unchanged; only the visual dimension is converted to a label.
 */
const normalizeNativeChartData = (type: string | undefined, data: Datum[]): Datum[] => {
  if (!['response_bar_chart', 'response_pie_chart', 'response_donut_chart'].includes(type || '') || !data.length)
    return data;
  const dimension = Object.keys(data[0] || {})[0];
  if (!dimension || !data.some(row => typeof row[dimension] === 'number')) return data;
  return data.map(row => ({ ...row, [dimension]: String(row[dimension]) }));
};

const nativeChartSpec = (
  artifact: ReportArtifact,
  artifacts: Map<string, ReportArtifact>,
): NativeChartSpec | undefined => {
  if (artifact.type !== 'chart') return undefined;
  const spec = artifact.spec as NativeChartSpec | undefined;
  if (spec?.renderer === 'vis-db-chart' && Array.isArray(spec.data)) {
    return { ...spec, data: normalizeNativeChartData(spec.type, spec.data as Datum[]) };
  }

  // Historical native-chart artifacts sometimes retained only their upstream
  // SQL result. Rebuild the native input from that real source rather than
  // leaving the report with an empty placeholder.
  const source = artifact.input_artifact_ids.map(id => artifacts.get(id)).find(Boolean);
  const data = tabularRows(source);
  const type = artifact.chart_type || 'response_table';
  return data.length ? { renderer: 'vis-db-chart', type, data: normalizeNativeChartData(type, data) } : undefined;
};

const NativeReportTable: React.FC<{ data: Datum[]; sourceIds: string[] }> = ({ data, sourceIds }) => {
  const columns = Array.from(new Set(data.flatMap(row => Object.keys(row))));
  if (!columns.length) return <div className='p-4 text-sm text-slate-500'>暂无可展示的查询结果</div>;
  return (
    <div className='max-w-full overflow-auto'>
      <table
        data-dbgpt-artifacts={sourceIds.join(',')}
        data-dbgpt-evidence-label='查询结果表'
        className='min-w-full border-collapse text-left text-sm'
      >
        <thead>
          <tr>
            {columns.map(column => (
              <th className='border-b bg-slate-50 px-3 py-2 font-semibold text-slate-700' key={column}>
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr key={index}>
              {columns.map(column => (
                <td className='border-b px-3 py-2 text-slate-700' key={column}>
                  <span
                    data-dbgpt-artifacts={sourceIds.join(',')}
                    data-dbgpt-evidence-label={`${column} · ${index + 1}`}
                  >
                    {String(row[column] ?? '')}
                  </span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

/** Render an actual DB-GPT AutoChart; the report layer supplies only its host. */
const NativeReportChart: React.FC<{
  artifactId: string;
  sourceIds: string[];
  spec: NativeChartSpec;
  onObserved: (
    artifactId: string,
    observation: Omit<BrowserRenderObservation, 'artifact_id' | 'observation_id'>,
  ) => void;
}> = ({ artifactId, sourceIds, spec, onObserved }) => {
  const observe = useCallback(
    (observation: Omit<BrowserRenderObservation, 'artifact_id' | 'observation_id'>) =>
      onObserved(artifactId, observation),
    [artifactId, onObserved],
  );
  const chartTypes = useMemo(() => reportChartTypes(spec.type), [spec.type]);
  const startedAt = useRef(performance.now());
  useEffect(() => {
    if (spec.type === 'response_table')
      observe({
        renderer: 'table',
        state: 'rendered',
        duration_ms: Math.max(0, Math.round(performance.now() - startedAt.current)),
      });
  }, [spec.type, observe]);
  const data = (Array.isArray(spec.data) ? spec.data : []) as Datum[];
  if (spec.type === 'response_table') return <NativeReportTable data={data} sourceIds={sourceIds} />;
  return <AutoChart data={data} chartType={chartTypes} showControls={false} onRenderObservation={observe} />;
};

const text = (value: unknown) => {
  if (value === null || value === undefined) return '';
  if (typeof value === 'string') return value.slice(0, 4_000);
  try {
    return JSON.stringify(value).slice(0, 4_000);
  } catch {
    return String(value).slice(0, 4_000);
  }
};

const bridgeHtml = (html: string) => {
  const bridge = `<style>
    [data-dbgpt-artifacts]{cursor:pointer!important;outline:2px solid transparent;outline-offset:3px;transition:outline-color .15s,box-shadow .15s}
    [data-dbgpt-artifacts]:hover,[data-dbgpt-artifacts]:focus{outline-color:#2563eb!important;box-shadow:0 0 0 5px rgba(37,99,235,.12)!important}
    .dbgpt-evidence-trigger{border:0!important;cursor:pointer!important;background:#eff6ff!important;color:#155eef!important;font:700 12px/1 system-ui,sans-serif!important;box-shadow:0 1px 4px rgba(15,23,42,.16)!important}
    .dbgpt-evidence-trigger--inline{display:inline-flex!important;align-items:center!important;justify-content:center!important;vertical-align:middle!important;margin-left:5px!important;min-width:19px!important;height:19px!important;padding:0 4px!important;border-radius:999px!important;font-size:9px!important}
    .dbgpt-evidence-host{position:relative!important;box-sizing:border-box!important}
    /* Keep a dedicated action area inside the existing report card.  Adding a
       sibling changes flex/grid templates into an extra card/column. */
    .dbgpt-evidence-host--reserve-corner{padding-right:58px!important}
    .dbgpt-evidence-trigger--corner{position:absolute!important;right:10px!important;top:10px!important;z-index:2147483646!important;display:grid!important;place-items:center!important;min-width:30px!important;height:30px!important;padding:0 8px!important;border-radius:999px!important}
    .dbgpt-evidence-table-caption{caption-side:top!important;padding:6px 10px!important;text-align:right!important}
    .dbgpt-evidence-trigger--table{position:relative!important;display:inline-flex!important;align-items:center!important;justify-content:center!important;min-width:30px!important;height:30px!important;padding:0 8px!important;border-radius:999px!important}
    .dbgpt-evidence-trigger:hover{background:#dbeafe!important;color:#1d4ed8!important}
    .dbgpt-evidence-value{font-weight:800!important;color:#0f3a8a!important;text-decoration:underline dotted #2563eb 2px;text-underline-offset:3px}
    .dbgpt-native-chart-host{display:block!important;width:100%!important;min-width:0!important;min-height:360px!important;overflow:hidden!important;position:relative!important}
    /* Evidence is an interactive review aid, not report content.  Browser
       print/PDF export uses this same srcdoc, so remove all controls and
       review-only affordances while preserving the actual numbers, charts,
       and narrative in the exported analysis report. */
    @media print {
      .dbgpt-evidence-trigger{display:none!important}
      [data-dbgpt-artifacts]{cursor:default!important;outline:0!important;box-shadow:none!important}
      .dbgpt-evidence-host--reserve-corner{padding-right:var(--dbgpt-evidence-print-padding-right, inherit)!important}
      .dbgpt-evidence-value{color:inherit!important;text-decoration:none!important;font-weight:inherit!important}
    }
  </style><script>
    (function () {
      var renderObservations = {};
      function observeChart(artifactId, renderer, state, started, options, error) {
        if (!artifactId || renderObservations[artifactId]) return;
        var serializable;
        try { serializable = options ? JSON.parse(JSON.stringify(options)) : undefined; } catch (ignore) {}
        var observation = { artifact_id: artifactId, renderer: renderer, state: state, duration_ms: Math.max(0, Math.round(performance.now() - started)), options: serializable };
        if (error) observation.error = String(error).slice(0, 2000);
        renderObservations[artifactId] = observation;
        parent.postMessage({ type: 'dbgpt-report-render-observation', observation: observation }, '*');
      }
      function observeECharts() {
        if (!window.echarts || window.echarts.init.dbgptObserved) return;
        var original = window.echarts.init;
        function init(dom) {
          var target = dom.closest('[data-dbgpt-chart-id]');
          var artifactId = target && target.getAttribute('data-dbgpt-chart-id');
          var started = performance.now();
          var chart;
          try { chart = original.apply(this, arguments); } catch (error) {
            observeChart(artifactId, 'echarts', 'failed', started, undefined, error); throw error;
          }
          if (!artifactId) return chart;
          var called = false;
          chart.on('finished', function () { if (called) observeChart(artifactId, 'echarts', 'rendered', started, chart.getOption()); });
          var setOption = chart.setOption;
          chart.setOption = function () {
            called = true;
            try { return setOption.apply(this, arguments); } catch (error) {
              observeChart(artifactId, 'echarts', 'failed', started, undefined, error); throw error;
            }
          };
          function reportUnusedChart() { window.setTimeout(function () {
            if (!called) observeChart(artifactId, 'echarts', 'not_rendered', started, undefined, 'No chart option was applied');
          }, 0); }
          if (document.readyState === 'complete') reportUnusedChart();
          else window.addEventListener('load', reportUnusedChart, { once: true });
          return chart;
        }
        init.dbgptObserved = true;
        window.echarts.init = init;
      }
      observeECharts();
      document.addEventListener('load', observeECharts, true);
      document.addEventListener('DOMContentLoaded', observeECharts);
      window.addEventListener('message', function (event) {
        if (event.source !== parent || !event.data || event.data.type !== 'dbgpt-report-artifact-types') return;
        Object.keys(renderObservations).forEach(function (id) {
          parent.postMessage({ type: 'dbgpt-report-render-observation', observation: renderObservations[id] }, '*');
        });
        var renderers = event.data.renderers || {};
        document.querySelectorAll('img').forEach(function (image) {
          var figure = image.closest('[data-dbgpt-artifacts]');
          if (!figure || image.dataset.dbgptObserved) return;
          var id = (figure.getAttribute('data-dbgpt-artifacts') || '').split(',').map(function (value) { return value.trim(); }).find(function (value) { return renderers[value] === 'image'; });
          if (!id) return;
          image.dataset.dbgptObserved = 'true';
          var started = performance.now();
          image.decode().then(function () { observeChart(id, 'image', 'rendered', started); }, function (error) { observeChart(id, 'image', 'failed', started, undefined, error); });
        });
      });
      var artifactTypes = {};
      var inferenceTargets = {};
      function emitEvidence(node) {
        if (!node) return;
        var artifactIds = (node.getAttribute('data-dbgpt-artifacts') || '').split(',').map(function (id) { return id.trim(); }).filter(Boolean);
        // srcdoc has an opaque ("null") location.origin. The receiving React
        // component validates event.source against its own iframe, so a wildcard
        // target is required here without accepting messages from other frames.
        if (artifactIds.length) parent.postMessage({ type: 'dbgpt-report-evidence', artifactIds: artifactIds, elementTag: node.tagName || '', blockId: node.getAttribute('data-dbgpt-block-id') || '', claimId: node.getAttribute('data-dbgpt-claim-id') || '', label: (node.getAttribute('data-dbgpt-evidence-label') || node.getAttribute('aria-label') || node.textContent || '').trim().slice(0, 160) }, '*');
      }
      function isInline(node) { return /^(STRONG|B|SPAN|EM|MARK|A)$/i.test(node.tagName); }
      function isTextBlock(node) { return /^(P|LI|H[1-6]|TD|TH|BLOCKQUOTE|LABEL|SUMMARY)$/i.test(node.tagName); }
      function isTableStructure(node) { return /^(TR|THEAD|TBODY|TFOOT|COLGROUP|COL)$/i.test(node.tagName); }
      function hasReferenceBinding(node) {
        return (node.getAttribute('data-dbgpt-artifacts') || '').split(',').some(function (id) { return id.trim().indexOf('reference-') === 0; });
      }
      function isChartContainer(node) {
        if (!node) return false;
        if (node.tagName === 'FIGURE') return true;
        if (node.matches('.chart-box,.chartbox,.figbox,[_echarts_instance_],[data-dbgpt-chart-placeholder]')) return true;
        var ids = (node.getAttribute('data-dbgpt-artifacts') || '').split(',').map(function (id) { return id.trim(); });
        // Captured native and generated chart artifacts use this stable ID
        // namespace.  A chart may initially be an empty .ph placeholder and
        // receive its SVG only after this bridge has decorated the document.
        return ids.some(function (id) { return id.indexOf('chart-') === 0; }) || Boolean(node.querySelector('.ph,.chartbox,.figbox,[data-dbgpt-chart-placeholder]'));
      }
      function hasBoundDescendant(node) {
        // A KB rule belongs to the containing metric, while its displayed
        // number belongs to the calculation. Keep both controls when a
        // reference is present; otherwise prefer the specific child claim.
        if (node.tagName === 'TABLE' || isTableStructure(node) || isChartContainer(node) || hasReferenceBinding(node)) return false;
        return Boolean(node.querySelector('[data-dbgpt-artifacts]:not([data-dbgpt-evidence-control="true"])'));
      }
      function tableControlHost(node) {
        var table = node.tagName === 'TABLE' ? node : node.closest('table');
        if (!table) return null;
        var caption = table.querySelector(':scope > caption.dbgpt-evidence-table-caption');
        if (!caption) {
          caption = document.createElement('caption');
          caption.className = 'dbgpt-evidence-table-caption';
          table.insertBefore(caption, table.firstChild);
        }
        return caption;
      }
      function removeNearestContainerControlForInlineClaims() {
        // The source HTML may have been progressively enhanced (or a chart
        // mounted) after the first decoration pass.  In that case the parent
        // card button can already exist before its value becomes a bound
        // <strong>.  Reconcile after all targets are decorated: a numeric
        // claim owns the visible control, while its *nearest* bound container
        // keeps the binding but loses only the duplicate pill.  Do not walk
        // past that nearest container, so a report section can still expose
        // its distinct SQL + KB methodology badge.
        Array.prototype.forEach.call(document.querySelectorAll('[data-dbgpt-artifacts]'), function (claim) {
          if (!isInline(claim) || claim.getAttribute('data-dbgpt-evidence-control') === 'true') return;
          var container = claim.parentElement && claim.parentElement.closest('[data-dbgpt-artifacts]');
          if (!container || container === claim || container.tagName === 'TABLE' || isTableStructure(container) || isChartContainer(container) || hasReferenceBinding(container)) return;
          Array.prototype.forEach.call(container.querySelectorAll(':scope > [data-dbgpt-evidence-control="true"]'), function (control) {
            control.remove();
          });
          container.classList.remove('dbgpt-evidence-host--reserve-corner');
        });
      }
      function decorateEvidenceTargets() {
        Array.prototype.forEach.call(document.querySelectorAll('[data-dbgpt-artifacts], [_echarts_instance_]'), function (node) {
          if (node.hasAttribute('data-dbgpt-evidence-summary') || node.getAttribute('data-dbgpt-evidence-control') === 'true') return;
          if (node.getAttribute('data-dbgpt-evidence-decorated') === 'true') return;
          var bindingNode = node;
          if (!node.hasAttribute('data-dbgpt-artifacts')) {
            // Historical template charts retain their real section source.
            // Reuse that persisted target; never invent an artifact or block ID.
            bindingNode = node.closest('[data-dbgpt-artifacts]');
            if (!bindingNode) return;
            if (bindingNode.tagName === 'FIGURE') {
              node.setAttribute('data-dbgpt-evidence-decorated', 'true');
              return;
            }
            var chart = window.echarts && window.echarts.getInstanceByDom(node);
            var option = chart && chart.getOption();
            var title = option && option.title && option.title[0] && option.title[0].text;
            var figure = document.createElement('figure');
            figure.style.margin = '0'; figure.style.minWidth = '0';
            figure.setAttribute('data-dbgpt-evidence-label', title || node.id || '图表');
            node.setAttribute('data-dbgpt-evidence-decorated', 'true');
            node.before(figure); figure.appendChild(node); node = figure;
          }
          var inline = isInline(node);
          var textBlock = !inline && isTextBlock(node);
          var tableBound = node.tagName === 'TABLE' || isTableStructure(node);
          var chartBound = isChartContainer(node);
          // Prefer a nested value/claim binding over a broad card binding.
          // This is presentation-only: both bindings remain in the report
          // schema so a user can still click whitespace on the card to inspect
          // its SQL + KB rule, while the number exposes only its own source.
          if (!inline && hasBoundDescendant(node)) {
            node.setAttribute('data-dbgpt-evidence-decorated', 'true');
            return;
          }
          var host = tableBound ? tableControlHost(node) : (inline ? node : (/^(CANVAS|SVG|IMG)$/i.test(node.tagName) ? node.parentElement : node));
          if (!host) return;
          node.setAttribute('data-dbgpt-evidence-decorated', 'true');
          if (inline) node.classList.add('dbgpt-evidence-value');
          else if (!textBlock) {
            host.style.setProperty('--dbgpt-evidence-print-padding-right', window.getComputedStyle(host).paddingRight);
            host.classList.add('dbgpt-evidence-host');
            if (!chartBound) host.classList.add('dbgpt-evidence-host--reserve-corner');
          }
          var control = document.createElement('button');
          control.type = 'button'; control.setAttribute('data-dbgpt-evidence-control', 'true');
          control.setAttribute('data-dbgpt-artifacts', bindingNode.getAttribute('data-dbgpt-artifacts') || '');
          if (bindingNode.getAttribute('data-dbgpt-block-id')) control.setAttribute('data-dbgpt-block-id', bindingNode.getAttribute('data-dbgpt-block-id'));
          if (bindingNode.getAttribute('data-dbgpt-claim-id')) control.setAttribute('data-dbgpt-claim-id', bindingNode.getAttribute('data-dbgpt-claim-id'));
          if (chartBound) control.setAttribute('data-dbgpt-evidence-chart', 'true');
          control.setAttribute('data-dbgpt-evidence-label', node.getAttribute('data-dbgpt-evidence-label') || node.textContent || '报告内容');
          control.setAttribute('data-dbgpt-evidence-element-tag', node.tagName || '');
          control.setAttribute('aria-label', '查看该内容的执行证据');
          control.title = '查看执行证据'; control.className = 'dbgpt-evidence-trigger ' + (tableBound ? 'dbgpt-evidence-trigger--table' : ((inline || textBlock) ? 'dbgpt-evidence-trigger--inline' : 'dbgpt-evidence-trigger--corner'));
          if (bindingNode !== node) control.title = '查看图表所在章节的数据来源';
          control.textContent = '⌁';
          control.addEventListener('click', function (event) { event.preventDefault(); event.stopPropagation(); emitEvidence(control); });
          if (inline) node.insertAdjacentElement('afterend', control); else host.appendChild(control);
        });
        removeNearestContainerControlForInlineClaims();
        updateEvidenceLabels();
      }
      document.addEventListener('click', function (event) {
        var node = event.target && event.target.closest && event.target.closest('[data-dbgpt-artifacts]');
      if (!node) return;
      event.preventDefault();
        emitEvidence(node);
      });
      document.addEventListener('keydown', function (event) {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        var node = event.target && event.target.closest && event.target.closest('[data-dbgpt-artifacts]');
        if (!node) return; event.preventDefault(); emitEvidence(node);
      });
      function updateEvidenceLabels() {
        Array.prototype.forEach.call(document.querySelectorAll('[data-dbgpt-evidence-control="true"]'), function (control) {
          var artifactIds = (control.getAttribute('data-dbgpt-artifacts') || '').split(',').map(function (id) { return id.trim(); }).filter(Boolean);
          // IDs are stable across report reloads.  Prefer them over a delayed
          // artifact-type message so an inline SQL claim can never inherit the
          // parent figure's chart label during native-chart recovery.
          var hasSqlArtifact = artifactIds.some(function (id) { return id.indexOf('sql-') === 0; });
          var hasChartArtifact = artifactIds.some(function (id) { return id.indexOf('chart-') === 0; });
          var hasKnowledgeArtifact = artifactIds.some(function (id) { return artifactTypes[id] === 'KB'; });
          var labels = artifactIds.map(function (id) { return artifactTypes[id]; }).filter(Boolean);
          if (control.getAttribute('data-dbgpt-evidence-element-tag') === 'TABLE') labels = labels.filter(function (value) { return value !== '图'; });
          labels = labels.filter(function (value, index) { return labels.indexOf(value) === index; });
          // The chart, governing KB rule, and calculated number have separate
          // visual targets even when their parent container shares evidence.
          var elementTag = control.getAttribute('data-dbgpt-evidence-element-tag') || '';
          var isChart = /^(FIGURE|IMG|CANVAS|SVG)$/i.test(elementTag);
          var isInlineClaim = /^(STRONG|B|SPAN|EM|MARK|A)$/i.test(elementTag);
          if (isChart && hasChartArtifact) labels = ['图'];
          else if (hasKnowledgeArtifact && !isInlineClaim) labels = ['KB'];
          else if (hasSqlArtifact || labels.indexOf('SQL') !== -1) labels = ['SQL'];
          if (control.getAttribute('data-dbgpt-evidence-chart') === 'true' && labels.indexOf('图') === -1) labels.unshift('图');
          var targetId = control.getAttribute('data-dbgpt-claim-id') || control.getAttribute('data-dbgpt-block-id') || '';
          if (inferenceTargets[targetId] && labels.indexOf('Agent') === -1) labels.push('Agent');
          if (labels.length) control.textContent = labels.slice(0, 3).join('·');
        });
      }
      window.addEventListener('message', function (event) {
        if (event.source !== parent || event.data?.type !== 'dbgpt-report-artifact-types') return;
        artifactTypes = event.data.types || {};
        inferenceTargets = event.data.inferenceTargets || {};
        updateEvidenceLabels();
      });
      if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', decorateEvidenceTargets); else decorateEvidenceTargets();
      window.addEventListener('load', decorateEvidenceTargets);
      var decorationPending = false;
      new MutationObserver(function (mutations) {
        var needsDecoration = mutations.some(function (mutation) {
          var chart = mutation.target.closest && mutation.target.closest('[_echarts_instance_]');
          if (chart && chart.getAttribute('data-dbgpt-evidence-decorated') !== 'true') return true;
          return Array.prototype.some.call(mutation.addedNodes, function (node) {
            return node.nodeType === 1 && node.getAttribute('data-dbgpt-evidence-control') !== 'true'
              && (node.matches('[data-dbgpt-artifacts],[_echarts_instance_]') || node.querySelector('[data-dbgpt-artifacts],[_echarts_instance_]'));
          });
        });
        if (!needsDecoration || decorationPending) return;
        decorationPending = true;
        requestAnimationFrame(function () { decorationPending = false; decorateEvidenceTargets(); });
      }).observe(document.documentElement, { childList: true, subtree: true });
    })();
  </script>`;
  return /<\/head\s*>/i.test(html) ? html.replace(/<\/head\s*>/i, `${bridge}</head>`) : `${bridge}${html}`;
};

const formatMilliseconds = (duration?: number) => {
  if (duration === undefined || duration === null) return '未采集';
  return duration === 0 ? '< 1 ms' : `${duration} ms`;
};

function formatArtifactDuration(artifact: ReportArtifact) {
  if (artifact.metadata?.duration_ms_is_recovery_placeholder === true) return '原始执行耗时未保存';
  const duration = artifact.timing?.server_execution_ms ?? artifact.duration_ms;
  if (
    ['chart_action.render', 'template_chart.prepare', 'report_chart.prepare'].includes(artifact.execution.action || '')
  ) {
    return `${formatMilliseconds(duration)}（服务端图表规格准备）`;
  }
  if (artifact.execution.action === 'code_interpreter.image' && duration === 0) {
    return '由上游 Python 生成；本图像产物未单独计时';
  }
  return duration === undefined || duration === null ? '-' : `${duration} ms`;
}

const sourceCategory = (artifact: ReportArtifact) => {
  if (artifact.reference_type === 'knowledge') return '知识库';
  if (artifact.reference_type === 'web') return '网页资料';
  if (artifact.reference_type === 'memory') return '会话记忆';
  if (artifact.reference_type === 'model') return '模型推理';
  if (artifact.reference_type === 'file') return '文件快照';
  if (artifact.database || artifact.type === 'sql') return '数据库';
  if (artifact.type === 'python') return 'Python 计算';
  if (artifact.type === 'chart') return '图表渲染';
  return '任务输入';
};

const referenceLocation = (artifact: ReportArtifact) => formatReferenceLocation(artifact.locator);

const formatSqlForDisplay = (sql: string) => {
  try {
    return formatSql(sql, { language: 'sqlite' });
  } catch {
    return sql;
  }
};

const CollapsibleCode: React.FC<{ title: string; content: string; format?: (content: string) => string }> = ({
  title,
  content,
  format,
}) => {
  const rendered = format ? format(content) : content;
  const isLong = rendered.length > 480 || rendered.split('\n').length > 8;
  if (!isLong)
    return (
      <>
        <h4 className='mt-4 text-xs font-semibold text-slate-700 dark:text-slate-200'>{title}</h4>
        <pre className='mt-2 max-h-48 overflow-auto rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-50'>
          {rendered}
        </pre>
      </>
    );
  return (
    <details className='mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-white/[0.04]'>
      <summary className='cursor-pointer text-xs font-semibold text-slate-700 dark:text-slate-200'>
        {title}（点击展开）
      </summary>
      <pre className='mt-3 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-slate-950 p-3 text-xs leading-5 text-slate-50'>
        {rendered}
      </pre>
    </details>
  );
};

const ArtifactDetail: React.FC<{
  artifact: ReportArtifact;
  citationQuote?: string;
  observation?: BrowserRenderObservation;
  knowledgeNames: KnowledgeSpaceNames;
}> = ({ artifact, citationQuote, observation, knowledgeNames }) => (
  <article className='rounded-xl border border-slate-200 p-4 dark:border-slate-700'>
    <div className='flex items-start justify-between gap-3'>
      <div>
        <p className='text-[11px] font-bold uppercase text-blue-600'>{artifact.type}</p>
        <h3 className='mt-1 break-all text-sm font-semibold text-slate-900 dark:text-white'>
          {artifactTitle(artifact)}
        </h3>
      </div>
      <span className='rounded-full bg-emerald-50 px-2 py-1 text-[11px] text-emerald-700'>
        {artifact.status || 'captured'}
      </span>
    </div>
    <dl className='mt-4 grid grid-cols-[104px_1fr] gap-y-2 text-xs text-slate-600 dark:text-slate-300'>
      <dt>执行耗时</dt>
      <dd>{formatArtifactDuration(artifact)}</dd>
      <dt>来源类型</dt>
      <dd>{sourceCategory(artifact)}</dd>
      {artifact.type !== 'python' && artifact.type !== 'chart' && (
        <>
          <dt>具体来源</dt>
          <dd className='break-all'>{artifactSourceName(artifact, knowledgeNames)}</dd>
        </>
      )}
    </dl>
    {artifact.sql && <CollapsibleCode title='执行 SQL' content={text(artifact.sql)} format={formatSqlForDisplay} />}
    {artifact.sql && citationQuote && <CollapsibleCode title='此数值绑定的 SQL 条件' content={citationQuote} />}
    {artifact.code && <CollapsibleCode title={`执行 ${artifact.language || 'Python'}`} content={text(artifact.code)} />}
    {artifact.reference_type && (
      <>
        <h4 className='mt-4 text-xs font-semibold text-slate-700 dark:text-slate-200'>引用来源</h4>
        <div className='mt-2 rounded-lg bg-teal-50 p-3 text-xs text-teal-950 dark:bg-teal-500/10 dark:text-teal-100'>
          <p className='font-semibold'>{artifact.source_name || artifact.source_id || artifact.reference_type}</p>
          <p className='mt-1 break-all text-teal-800 dark:text-teal-200'>引用位置：{referenceLocation(artifact)}</p>
          {artifact.uri && <p className='mt-1 break-all text-teal-800 dark:text-teal-200'>{artifact.uri}</p>}
          {citationQuote && (
            <>
              <p className='mt-3 font-semibold'>报告引用原文</p>
              <blockquote className='mt-1 border-l-2 border-teal-500 pl-2 whitespace-pre-wrap leading-5'>
                {text(citationQuote)}
              </blockquote>
            </>
          )}
          {artifact.excerpt && (
            <details className='mt-2'>
              <summary className='cursor-pointer text-teal-800 dark:text-teal-200'>
                {artifact.locator?.chunk_id ? '查看引用切片内容' : '查看引用文档内容'}
              </summary>
              <p className='mt-2 whitespace-pre-wrap leading-5'>{text(artifact.excerpt)}</p>
            </details>
          )}
        </div>
      </>
    )}
    {artifact.result?.inline !== undefined && (
      <>
        <h4 className='mt-4 text-xs font-semibold text-slate-700 dark:text-slate-200'>结果快照</h4>
        <pre className='mt-2 max-h-36 overflow-auto rounded-lg bg-emerald-50 p-3 text-xs text-emerald-950 dark:bg-emerald-500/10 dark:text-emerald-100'>
          {text(artifact.result.inline)}
        </pre>
      </>
    )}
    {artifact.type === 'chart' && artifact.spec && (
      <CollapsibleCode title='图表规格与数据选择器' content={text(artifact.spec)} />
    )}
    {observation?.error && <p className='mt-3 text-xs text-red-600'>{observation.error}</p>}
  </article>
);

export const HtmlReportEvidence: React.FC<Props> = ({ html, reportId, reportRunId, iframeRef }) => {
  const ownedIframeRef = useRef<HTMLIFrameElement>(null);
  const reportIframeRef = iframeRef || ownedIframeRef;
  const [run, setRun] = useState<ReportRun>();
  const knowledgeNames = useKnowledgeSpaceNames(run?.document.artifacts || []);
  const runReady = run?.report_id === reportId && run?.run_id === reportRunId;
  const [error, setError] = useState('');
  const [selection, setSelection] = useState<{
    artifactIds: string[];
    elementTag?: string;
    blockId?: string;
    claimId?: string;
    label: string;
  }>();
  const [iframeDocument, setIframeDocument] = useState<Document>();
  const [observations, setObservations] = useState<Record<string, BrowserRenderObservation>>({});
  const [observationError, setObservationError] = useState('');
  const observationSession = useRef(`${Date.now()}-${Math.random().toString(36).slice(2)}`);
  const submitted = useRef(new Set<string>());
  const onObserved = useCallback(
    (artifactId: string, observation: Omit<BrowserRenderObservation, 'artifact_id' | 'observation_id'>) => {
      if (
        !runReady ||
        !run?.document.artifacts.some(a => a.artifact_id === artifactId && a.type === 'chart') ||
        submitted.current.has(artifactId)
      )
        return;
      submitted.current.add(artifactId);
      const value = { ...observation, artifact_id: artifactId, observation_id: observationSession.current };
      void saveRenderObservation(reportId, reportRunId, value)
        .then(result => {
          if (!result.success) throw new Error(result.err_msg || '浏览器观测保存失败');
          setObservations(previous => ({ ...previous, [artifactId]: result.data }));
        })
        .catch(reason => {
          submitted.current.delete(artifactId);
          setObservationError(String(reason));
        });
    },
    [run, runReady, reportId, reportRunId],
  );
  useEffect(() => {
    let alive = true;
    setObservations({});
    submitted.current.clear();
    setObservationError('');
    if (!runReady) return;
    void getRenderObservations(reportId, reportRunId)
      .then(result => {
        if (alive && result.success)
          setObservations(previous => ({
            ...Object.fromEntries([...result.data].reverse().map(item => [item.artifact_id, item])),
            ...previous,
          }));
      })
      .catch(reason => {
        if (alive) setObservationError(String(reason));
      });
    return () => {
      alive = false;
    };
  }, [reportId, reportRunId, runReady]);
  useEffect(() => {
    const listener = (event: MessageEvent) => {
      if (
        event.source !== reportIframeRef.current?.contentWindow ||
        event.data?.type !== 'dbgpt-report-render-observation'
      )
        return;
      const item = event.data.observation as BrowserRenderObservation;
      if (item && typeof item.artifact_id === 'string')
        onObserved(item.artifact_id, {
          renderer: item.renderer,
          state: item.state,
          duration_ms: item.duration_ms,
          options: item.options,
          error: item.error,
        });
    };
    window.addEventListener('message', listener);
    return () => window.removeEventListener('message', listener);
  }, [onObserved, reportIframeRef]);
  const [nativeChartMounts, setNativeChartMounts] = useState<NativeChartMount[]>([]);
  useEffect(() => {
    let alive = true;
    const load = async () => {
      let lastError = '报告证据暂不可用';
      for (let attempt = 0; attempt < 5 && alive; attempt += 1) {
        try {
          const result = await getStandaloneReportRun(reportId, reportRunId);
          if (alive && result.success) {
            setRun(result.data);
            setError('');
            return;
          }
          lastError = result.err_msg || lastError;
        } catch (reason) {
          lastError = reason instanceof Error ? reason.message : lastError;
        }
        await new Promise(resolve => window.setTimeout(resolve, 600 * (attempt + 1)));
      }
      if (alive) setError(lastError);
    };
    void load();
    return () => {
      alive = false;
    };
  }, [reportId, reportRunId]);
  const sendArtifactTypes = useCallback(() => {
    if (!run) return;
    const labels: Record<string, string> = { sql: 'SQL', python: 'PY', chart: '图' };
    const referenceLabels: Record<string, string> = {
      knowledge: 'KB',
      web: 'WEB',
      memory: '记忆',
      model: '模型',
      file: '文件',
    };
    const types = Object.fromEntries(
      run.document.artifacts.map(artifact => [
        artifact.artifact_id,
        artifact.type === 'reference'
          ? referenceLabels[artifact.reference_type || ''] || '来源'
          : labels[artifact.type] || artifact.type.toUpperCase(),
      ]),
    );
    const inferenceTargets: Record<string, boolean> = {};
    const inferredClaimTypes = new Set(['comparison', 'trend', 'ranking', 'aggregation', 'causal', 'recommendation']);
    run.document.sections
      .flatMap(section => section.blocks)
      .forEach(block => {
        const presentationTarget = block.metadata?.presentation_target as { target_id?: string } | undefined;
        if (presentationTarget?.target_id && block.metadata?.evidence_inference === true) {
          inferenceTargets[presentationTarget.target_id] = true;
        }
        (block.claims || []).forEach(claim => {
          if (inferredClaimTypes.has(claim.claim_type || '')) inferenceTargets[claim.claim_id] = true;
        });
      });
    const renderers = Object.fromEntries(
      run.document.artifacts
        .filter(a => a.type === 'chart')
        .map(a => [
          a.artifact_id,
          a.chart_type === 'image' ? 'image' : a.spec?.renderer === 'echarts' ? 'echarts' : 'g2',
        ]),
    );
    reportIframeRef.current?.contentWindow?.postMessage(
      { type: 'dbgpt-report-artifact-types', types, inferenceTargets, renderers },
      window.location.origin,
    );
  }, [reportIframeRef, run]);
  useEffect(() => {
    sendArtifactTypes();
  }, [sendArtifactTypes]);
  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.source !== reportIframeRef.current?.contentWindow || event.data?.type !== 'dbgpt-report-evidence')
        return;
      setSelection({
        artifactIds: Array.isArray(event.data.artifactIds) ? event.data.artifactIds : [],
        elementTag: String(event.data.elementTag || '') || undefined,
        blockId: String(event.data.blockId || '') || undefined,
        claimId: String(event.data.claimId || '') || undefined,
        label: String(event.data.label || '报告内容'),
      });
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [reportIframeRef]);
  const selectedBlock = useMemo(
    () =>
      run?.document.sections
        .flatMap(section => section.blocks)
        .find(block => {
          if (selection?.blockId && block.block_id === selection.blockId) return true;
          const target = block.metadata?.presentation_target as { kind?: string; target_id?: string } | undefined;
          return Boolean(selection?.claimId && target?.kind === 'html_claim' && target.target_id === selection.claimId);
        }),
    [run, selection?.blockId, selection?.claimId],
  );
  const artifacts = useMemo(() => {
    const byId = new Map(run?.document.artifacts.map(item => [item.artifact_id, item]));
    const artifactIds = selectedBlock?.evidence.map(item => item.artifact_id) || selection?.artifactIds || [];
    return artifactIds
      .map(id => byId.get(id))
      .filter(
        (item): item is ReportArtifact =>
          item !== undefined && (selection?.elementTag !== 'TABLE' || item.type !== 'chart'),
      );
  }, [run, selection, selectedBlock]);
  const citationQuotes = useMemo(
    () =>
      new Map(
        (selectedBlock?.evidence || []).map(evidence => [
          evidence.artifact_id,
          typeof evidence.selector?.quoted_text === 'string'
            ? evidence.selector.quoted_text
            : evidence.selector?.kind === 'sql' && typeof evidence.selector.quote === 'string'
              ? evidence.selector.quote
              : undefined,
        ]),
      ),
    [selectedBlock],
  );
  const nativeCharts = useMemo(() => {
    const sourceArtifacts = run?.document.artifacts || [];
    const artifactIndex = new Map(sourceArtifacts.map(artifact => [artifact.artifact_id, artifact]));
    return sourceArtifacts
      .map(artifact => ({ artifact, spec: nativeChartSpec(artifact, artifactIndex) }))
      .filter(
        (item): item is { artifact: ReportArtifact; spec: NativeChartSpec } =>
          item.artifact.execution.action === 'chart_action.render' && item.spec?.renderer === 'vis-db-chart',
      );
  }, [run]);
  const persistedPresentation = run?.document.metadata?.presentation as
    { format?: string; content?: string; trusted_template_scripts?: boolean } | undefined;
  // Reports generated before `trusted_template_scripts` was persisted still
  // exist in users' history.  Migrate only the narrow, server-observable case:
  // an executed skill script produced an ECharts template report.  This is not
  // inferred from a user prompt or arbitrary model HTML, and new reports use
  // the explicit backend flag above.
  const legacyTrustedSkillTemplate = Boolean(
    persistedPresentation?.format === 'html' &&
    (run?.document.artifacts || []).some(artifact => artifact.execution.action === 'execute_skill_script_file') &&
    /<script\b[^>]*https:\/\/cdn\.jsdelivr\.net\/npm\/echarts@|\becharts\.init\s*\(/i.test(
      persistedPresentation?.content || html,
    ),
  );
  const reportHtml = sanitizeEmbeddedReportHtml(
    persistedPresentation?.format === 'html' && persistedPresentation.content ? persistedPresentation.content : html,
    persistedPresentation?.trusted_template_scripts === true || legacyTrustedSkillTemplate,
  );
  useEffect(() => {
    setIframeDocument(undefined);
    setNativeChartMounts([]);
  }, [reportHtml]);
  const presentationStatus = String(run?.document.metadata?.presentation_status || '');
  const noPresentationMessage =
    presentationStatus === 'not_generated'
      ? '本轮仅保存了执行证据，未完成 HTML 报告生成。请重新执行或从最后一个失败步骤继续。'
      : '本轮尚未生成 HTML 报告时，不会以执行产物卡片替代报告。';
  const onIframeDocumentReady = useCallback(
    (document: Document) => {
      sendArtifactTypes();
      setIframeDocument(document);
    },
    [sendArtifactTypes],
  );
  useEffect(() => {
    if (!iframeDocument) return;
    // Remove mounts created by an earlier report version / hot reload before
    // calculating the current targets. Without this, a formerly table-bound
    // chart host remains in the iframe even after the selection rule is fixed.
    iframeDocument
      .querySelectorAll('[data-dbgpt-native-chart-host], [data-dbgpt-auto-native-chart-container]')
      .forEach(host => host.remove());
    const mounts: NativeChartMount[] = [];
    nativeCharts.forEach(({ artifact, spec }) => {
      let target = Array.from(iframeDocument.querySelectorAll<HTMLElement>('[data-dbgpt-artifacts]')).find(node => {
        const isBound = (node.getAttribute('data-dbgpt-artifacts') || '')
          .split(',')
          .map(id => id.trim())
          .includes(artifact.artifact_id);
        if (!isBound || node.tagName === 'TABLE') return false;
        // An empty figure is an explicit chart placeholder.  For legacy
        // malformed image markup, retain the in-place repair path as well.
        // Do not append charts to generic text/card containers.
        return (
          node.tagName === 'FIGURE' ||
          Boolean(node.querySelector('img,canvas,svg,.ph,.chartbox,.figbox,[data-dbgpt-chart-placeholder]'))
        );
      });
      // Compatibility for persisted reports created before the backend added
      // the separate figure. The source SQL table is an explicit rendered
      // report object, so this restores its already-executed native chart
      // without generating a new chart or binding a chart artifact to a table.
      if (!target) {
        const sourceIds = artifact.input_artifact_ids || [];
        const sourceTable = Array.from(
          iframeDocument.querySelectorAll<HTMLTableElement>('table[data-dbgpt-artifacts]'),
        ).find(table =>
          sourceIds.some(sourceId =>
            (table.getAttribute('data-dbgpt-artifacts') || '')
              .split(',')
              .map(id => id.trim())
              .includes(sourceId),
          ),
        );
        if (sourceTable) {
          const figure = iframeDocument.createElement('figure');
          figure.setAttribute('data-dbgpt-auto-native-chart-container', 'true');
          figure.setAttribute('data-dbgpt-artifacts', [...new Set([...sourceIds, artifact.artifact_id])].join(','));
          figure.setAttribute('data-dbgpt-evidence-label', artifact.name || '原生分析图表');
          sourceTable.before(figure);
          target = figure;
        }
      }
      if (!target || target.querySelector(`[data-dbgpt-native-chart-host="${artifact.artifact_id}"]`)) return;
      const visual = target.querySelector('img,canvas,svg');
      // `visual` belongs to the report iframe, so it must not be checked with
      // the parent window's HTMLImageElement constructor. Cross-window
      // `instanceof` returns false and previously made `<img src="">` look
      // like an already-rendered visual, skipping native chart recovery.
      const image = visual?.tagName === 'IMG' ? (visual as HTMLImageElement) : null;
      // Native DB-GPT report templates use `.ph`, `.chartbox`, and `.figbox`
      // as chart placeholders.  Appending the recovered chart after one of
      // them leaves a blank panel above the actual visual, so replace it in
      // place instead.
      const placeholder = target.matches('.ph, .chartbox, .figbox, [data-dbgpt-chart-placeholder]')
        ? target
        : target.querySelector<HTMLElement>('.ph, .chartbox, .figbox, [data-dbgpt-chart-placeholder]');
      const source = image?.getAttribute('src') || '';
      const validImage = /^(?:https?:|\/images\/|data:image\/)/i.test(source);
      if (visual && (!image || validImage)) return;
      // Native chart_query records a complete DB-GPT chart specification. Some
      // older reports bind it to an otherwise empty <figure> (or write prose
      // into img.src) but omit the rendered node. Restore only that missing
      // visual in the already-bound non-table target; never alter cards, tables,
      // or unrelated template content.
      const host = iframeDocument.createElement('div');
      host.className = 'dbgpt-native-chart-host';
      host.setAttribute('data-dbgpt-native-chart-host', artifact.artifact_id);
      // The report template uses `.ph` as a visual placeholder for a native
      // chart. Replace it in place; appending after it leaves a large blank
      // panel above the actual chart and can push the portal out of view.
      if (image) image.replaceWith(host);
      else if (placeholder && placeholder !== target) placeholder.replaceWith(host);
      else if (placeholder === target) {
        target.replaceChildren(host);
        target.classList.remove('ph', 'chartbox', 'figbox');
        target.style.minHeight = '0';
        target.style.height = 'auto';
        target.style.padding = '0';
        target.style.border = '0';
      } else target.appendChild(host);
      mounts.push({ artifact, spec, host });
      // The report author binds the figure to both the source SQL and its
      // generated chart artifact.  Make that relationship explicit on the
      // already-injected control as well: otherwise a control created before
      // the native-chart portal mounts can misleadingly display only “SQL”.
      // Do not promote the chart artifact onto nested inline number controls:
      // their SQL bindings are intentionally more specific than the figure's
      // SQL + chart binding.  Only the figure/container control represents
      // the rendered chart.
      let evidenceControls = Array.from(
        target.querySelectorAll<HTMLButtonElement>('[data-dbgpt-evidence-control="true"]'),
      ).filter(
        control =>
          control.getAttribute('data-dbgpt-evidence-element-tag') === 'FIGURE' || control.parentElement === target,
      );
      // Historical reports can receive the figure only after the iframe bridge
      // has decorated the original DOM. Give that recovered native chart the
      // same compact, clickable Chart evidence badge as a newly persisted
      // figure, rather than leaving the chart visually untraceable.
      if (!evidenceControls.length) {
        target.classList.add('dbgpt-evidence-host', 'dbgpt-evidence-host--reserve-corner');
        const control = iframeDocument.createElement('button');
        control.type = 'button';
        control.className = 'dbgpt-evidence-trigger dbgpt-evidence-trigger--corner';
        control.setAttribute('data-dbgpt-evidence-control', 'true');
        control.setAttribute(
          'data-dbgpt-artifacts',
          target.getAttribute('data-dbgpt-artifacts') || artifact.artifact_id,
        );
        control.setAttribute('data-dbgpt-evidence-element-tag', 'FIGURE');
        control.setAttribute(
          'data-dbgpt-evidence-label',
          target.getAttribute('data-dbgpt-evidence-label') || artifact.name || '原生分析图表',
        );
        control.title = '查看图表及其数据证据';
        control.setAttribute('aria-label', '查看图表及其数据证据');
        control.addEventListener('click', event => {
          event.preventDefault();
          event.stopPropagation();
          const artifactIds = (control.getAttribute('data-dbgpt-artifacts') || '')
            .split(',')
            .map(id => id.trim())
            .filter(Boolean);
          iframeDocument.defaultView?.parent.postMessage(
            {
              type: 'dbgpt-report-evidence',
              artifactIds,
              elementTag: 'FIGURE',
              label: control.getAttribute('data-dbgpt-evidence-label') || '原生分析图表',
            },
            '*',
          );
        });
        target.appendChild(control);
        evidenceControls = [control];
      }
      evidenceControls.forEach(control => {
        const artifactIds = (control.getAttribute('data-dbgpt-artifacts') || '')
          .split(',')
          .map(id => id.trim())
          .filter(Boolean);
        if (!artifactIds.includes(artifact.artifact_id)) {
          artifactIds.push(artifact.artifact_id);
          control.setAttribute('data-dbgpt-artifacts', artifactIds.join(','));
        }
        control.textContent = '图';
        control.title = '查看图表及其数据证据';
        control.setAttribute('aria-label', '查看图表及其数据证据');
      });
    });
    setNativeChartMounts(mounts);
  }, [iframeDocument, nativeCharts]);
  return (
    <div className='flex h-full min-h-0 bg-slate-100 dark:bg-[#111217]'>
      <div className='min-w-0 flex-1 overflow-auto'>
        {reportHtml.trim() ? (
          <ReportIframe
            iframeRef={reportIframeRef}
            onDocumentReady={onIframeDocumentReady}
            title='分析报告'
            srcDoc={bridgeHtml(resolveReportAssetUrls(reportHtml))}
            minHeight={320}
          />
        ) : (
          <div className='grid h-full min-h-[360px] place-items-center p-8 text-center'>
            <div>
              <p className='text-sm font-medium text-slate-700 dark:text-white'>本轮未生成 HTML 分析报告</p>
              <p className='mt-2 text-xs text-slate-500'>{error || noPresentationMessage}</p>
            </div>
          </div>
        )}
        {nativeChartMounts.map(({ artifact, spec, host }) =>
          createPortal(
            <NativeReportChart
              artifactId={artifact.artifact_id}
              sourceIds={artifact.input_artifact_ids.filter(id =>
                run?.document.artifacts.some(
                  source => source.artifact_id === id && ['sql', 'python'].includes(source.type),
                ),
              )}
              spec={spec}
              onObserved={onObserved}
            />,
            host,
            artifact.artifact_id,
          ),
        )}
      </div>
      {selection && (
        <aside className='z-10 w-[420px] shrink-0 overflow-y-auto border-l border-slate-200 bg-white shadow-2xl dark:border-slate-700 dark:bg-[#191a1f]'>
          <header className='sticky top-0 border-b border-slate-100 bg-white px-5 py-4 dark:border-slate-800 dark:bg-[#191a1f]'>
            <div className='flex items-start justify-between gap-3'>
              <div>
                <p className='text-xs font-bold text-blue-600'>证据详情</p>
                <h2 className='mt-1 text-base font-semibold text-slate-900 dark:text-white'>
                  {selection.label || '报告内容'}
                </h2>
              </div>
              <button
                type='button'
                onClick={() => setSelection(undefined)}
                className='rounded px-2 text-xl text-slate-400 hover:bg-slate-100'
              >
                ×
              </button>
            </div>
          </header>
          <div className='space-y-4 p-5'>
            {observationError && <p className='text-xs text-amber-700'>图表观测失败：{observationError}</p>}
            {!run && <p className='text-sm text-slate-500'>{error || '正在加载证据…'}</p>}
            {run && !artifacts.length && (
              <p className='rounded-lg bg-amber-50 p-3 text-sm text-amber-800'>
                该报告元素引用的证据不存在于本次运行中。
              </p>
            )}
            {artifacts.map(artifact => (
              <ArtifactDetail
                key={artifact.artifact_id}
                artifact={artifact}
                citationQuote={citationQuotes.get(artifact.artifact_id)}
                observation={observations[artifact.artifact_id]}
                knowledgeNames={knowledgeNames}
              />
            ))}
          </div>
        </aside>
      )}
      {!selection && (
        <div className='pointer-events-none absolute bottom-5 right-5 max-w-xs rounded-xl border border-blue-100 bg-white/95 p-3 text-xs leading-5 text-slate-600 shadow-lg dark:border-blue-500/30 dark:bg-[#191a1f]/95 dark:text-slate-300'>
          {error ? '当前报告证据尚不可用。' : '带“证据”标记的指标、图表和结论可点击查看其执行依据。'}
        </div>
      )}
    </div>
  );
};

export default HtmlReportEvidence;
