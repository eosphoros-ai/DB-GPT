/**
 * Approval policy setting page (design doc §4.5).
 *
 * L2 store UI: global mode, per-tool tier overrides, rule editor with a
 * classify playground, whitelist management and scalar params. Changes are
 * kept in a local draft and committed as one batch (POST /policy/save),
 * which writes the audit diff server-side.
 */
import { WarningOutlined } from '@ant-design/icons';
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

const API = process.env.API_BASE_URL ?? '';

interface PolicyRule {
  id: number;
  kind: string;
  tool: string;
  arg_pattern: string | null;
  tier: string;
  locked: boolean;
  source: string;
}
interface PolicyView {
  mode: string;
  ttl_seconds: number;
  intent_analysis: boolean;
  fail_safe: string;
  tool_overrides: PolicyRule[];
  rules: PolicyRule[];
  version: number;
}
interface TraceLine {
  rule_id: string;
  tier: string;
  hit: boolean;
}

const TOOL_OPTIONS = ['bash', 'code', 'sql_query', 'web_fetch'];
const TIERS = ['rules', 'auto', 'confirm', 'deny'];

const card =
  'rounded-xl border border-[#e6e6e2] bg-white p-4 shadow-[0_1px_2px_rgba(20,20,15,.05)] dark:border-[#33353b] dark:bg-[#1e1f24]';
const label = 'text-[12px] font-medium uppercase tracking-wider text-[#8b8b84]';

export default function ApprovalSettingsPage() {
  const { t } = useTranslation();
  const tierLabel = (tier: string) => t(`setting_tier_${tier}`);
  const [view, setView] = useState<PolicyView | null>(null);
  const [error, setError] = useState('');
  // draft
  const [mode, setMode] = useState('tiered');
  const [ttl, setTtl] = useState(300);
  const [intent, setIntent] = useState(true);
  const [failSafe, setFailSafe] = useState('confirm');
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [deletedRuleIds, setDeletedRuleIds] = useState<number[]>([]);
  const [addedRules, setAddedRules] = useState<{ tool: string; arg_pattern: string; tier: string }[]>([]);
  // rule add form
  const [newTool, setNewTool] = useState('bash');
  const [newPattern, setNewPattern] = useState('');
  const [newTier, setNewTier] = useState('confirm');
  // playground
  const [pgTool, setPgTool] = useState('bash');
  const [pgText, setPgText] = useState('');
  const [pgResult, setPgResult] = useState<{ verdict: [string, string]; trace: TraceLine[] } | null>(null);
  // whitelist
  const [wlConv, setWlConv] = useState('');
  const [wl, setWl] = useState<{ scope: string; signature: string; conv_id: string | null }[]>([]);

  const load = useCallback(async () => {
    const res = await fetch(`${API}/api/v1/chat/approval/policy`);
    const json = await res.json();
    if (!json.success) throw new Error(json.err_msg || 'load failed');
    const v: PolicyView = json.data;
    setView(v);
    setMode(v.mode);
    setTtl(v.ttl_seconds);
    setIntent(v.intent_analysis);
    setFailSafe(v.fail_safe);
    const ov: Record<string, string> = {};
    for (const o of v.tool_overrides) ov[o.tool] = o.tier;
    setOverrides(ov);
    setDeletedRuleIds([]);
    setAddedRules([]);
  }, []);

  useEffect(() => {
    // Deep links: ?mode= drafts a mode change (save bar demo / shareable
    // state), ?tool=&try= auto-runs the playground (shareable trial links).
    const q = new URLSearchParams(window.location.search);
    const modeParam = q.get('mode');
    if (modeParam === 'off' || modeParam === 'tiered' || modeParam === 'always') {
      setMode(modeParam);
    }
    const tryText = q.get('try');
    const rawTool = q.get('tool') || 'bash';
    const tryTool =
      rawTool === 'shell_interpreter'
        ? 'bash'
        : rawTool === 'code_interpreter'
          ? 'code'
          : rawTool;
    if (tryText) {
      setPgTool(tryTool);
      setPgText(tryText);
    }
    load()
      .then(() => {
        if (tryText) return runPlayground(tryTool, tryText);
        return undefined;
      })
      .catch(e => setError(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadWhitelist = useCallback(async () => {
    const res = await fetch(`${API}/api/v1/chat/approval/whitelist?con_uid=${encodeURIComponent(wlConv)}`);
    const json = await res.json();
    if (json.success) setWl(json.data);
  }, [wlConv]);

  const dirty = useMemo(() => {
    if (!view) return 0;
    let n = 0;
    if (mode !== view.mode) n++;
    if (ttl !== view.ttl_seconds) n++;
    if (intent !== view.intent_analysis) n++;
    if (failSafe !== view.fail_safe) n++;
    for (const o of view.tool_overrides) if (overrides[o.tool] && overrides[o.tool] !== o.tier) n++;
    for (const t of TOOL_OPTIONS)
      if (overrides[t] && !view.tool_overrides.some(o => o.tool === t)) n++;
    n += deletedRuleIds.length + addedRules.length;
    return n;
  }, [view, mode, ttl, intent, failSafe, overrides, deletedRuleIds, addedRules]);

  const save = async () => {
    setError('');
    const tool_overrides = Object.entries(overrides)
      .filter(([tool, tier]) => {
        const cur = view?.tool_overrides.find(o => o.tool === tool);
        return cur ? cur.tier !== tier : tier !== 'rules';
      })
      .map(([tool, tier]) => ({ tool, tier }));
    const res = await fetch(`${API}/api/v1/chat/approval/policy/save`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        mode,
        ttl_seconds: ttl,
        intent_analysis: intent,
        fail_safe: failSafe,
        tool_overrides,
        add_rules: addedRules,
        delete_rule_ids: deletedRuleIds,
      }),
    });
    const json = await res.json();
    if (!json.success) {
      setError(json.err_msg || 'save failed');
      return;
    }
    await load();
  };

  const addRule = () => {
    const pattern = newPattern.trim();
    if (!pattern) return;
    setAddedRules(prev => [...prev, { tool: newTool, arg_pattern: pattern, tier: newTier }]);
    setNewPattern('');
  };

  const runPlayground = async (toolArg?: string, textArg?: string) => {
    const tool = toolArg ?? pgTool;
    const text = textArg ?? pgText;
    const res = await fetch(`${API}/api/v1/chat/approval/policy/playground`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tool, text }),
    });
    const json = await res.json();
    if (json.success) setPgResult(json.data);
    else setError(json.err_msg || 'playground failed');
  };

  if (!view) return <div className='p-8 text-sm text-[#8b8b84]'>{t('setting_loading')}{error && `（${error}）`}</div>;

  return (
    <div className='mx-auto max-w-[860px] space-y-4 p-6 pb-24'>
      <div className='flex items-center gap-2'>
        <WarningOutlined className='text-[#dc2626]' />
        <h1 className='text-[17px] font-semibold text-[#1c1c1a] dark:text-[#e6e4df]'>{t('setting_title')}</h1>
        <span className='ml-auto font-mono text-[11px] text-[#8b8b84]'>v{view.version}</span>
      </div>
      {error && <div className='rounded-lg bg-red-50 px-3 py-2 text-[13px] text-[#dc2626]'>{error}</div>}

      {/* mode */}
      <section className={card}>
        <div className={label}>{t('setting_mode')}</div>
        <div className='mt-2 flex gap-1'>
          {['off', 'tiered', 'always'].map(m => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`h-8 rounded-lg px-4 text-[13px] ${
                mode === m
                  ? 'bg-[#1c1c1a] text-white dark:bg-white dark:text-black'
                  : 'border border-[#e6e6e2] text-[#5c5c55] dark:border-[#33353b]'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
        {mode !== 'tiered' && (
          <div className='mt-2 text-[12.5px] text-[#b45353]'>
            {mode === 'off' ? t('setting_mode_off_warn') : t('setting_mode_always_warn')}
          </div>
        )}
      </section>

      {/* tool overrides */}
      <section className={card}>
        <div className={label}>{t('setting_tools')}</div>
        <table className='mt-2 w-full text-[13px]'>
          <tbody>
            {Array.from(new Set([...TOOL_OPTIONS, ...view.tool_overrides.map(o => o.tool)])).map(tool => {
              const ov = view.tool_overrides.find(o => o.tool === tool);
              return (
                <tr key={tool} className='border-t border-[#f0f0ec] dark:border-[#2a2b30]'>
                  <td className='py-2 font-mono text-[12.5px]'>{tool}</td>
                  <td className='py-2 text-[12px] text-[#8b8b84]'>{ov?.locked ? t('setting_locked') : ov ? `${t('setting_source')} ${ov.source}` : t('setting_src_builtin')}</td>
                  <td className='py-2 text-right'>
                    <select
                      value={overrides[tool] ?? 'rules'}
                      disabled={ov?.locked}
                      onChange={e => setOverrides(prev => ({ ...prev, [tool]: e.target.value }))}
                      className='h-8 rounded-lg border border-[#e6e6e2] bg-white px-2 text-[12.5px] disabled:opacity-40 dark:border-[#33353b] dark:bg-[#17181c]'
                    >
                      {TIERS.map(t => (
                        <option key={t} value={t}>
                          {tierLabel(t)}
                        </option>
                      ))}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {/* rules + playground */}
      <section className={card}>
        <div className={label}>{t('setting_rules')}</div>
        <table className='mt-2 w-full text-[12.5px]'>
          <tbody>
            {view.rules
              .filter(r => !deletedRuleIds.includes(r.id))
              .map(r => (
                <tr key={r.id} className='border-t border-[#f0f0ec] dark:border-[#2a2b30]'>
                  <td className='py-1.5 font-mono'>{r.tool}</td>
                  <td className='py-1.5 font-mono text-[#5c5c55]'>{r.arg_pattern}</td>
                  <td className='py-1.5'>{r.tier}</td>
                  <td className='py-1.5 text-[#8b8b84]'>{r.locked ? t('setting_locked') : r.source}</td>
                  <td className='py-1.5 text-right'>
                    {!r.locked && (
                      <button
                        className='text-[12px] text-[#b45353] hover:underline'
                        onClick={() => setDeletedRuleIds(prev => [...prev, r.id])}
                      >
                        {t('setting_delete')}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            {addedRules.map((r, i) => (
              <tr key={`new-${i}`} className='border-t border-[#f0f0ec] text-[#3f7a3f] dark:border-[#2a2b30]'>
                <td className='py-1.5 font-mono'>{r.tool}</td>
                <td className='py-1.5 font-mono'>{r.arg_pattern}</td>
                <td className='py-1.5'>{r.tier}</td>
                <td className='py-1.5'>{t('setting_row_new')}</td>
                <td className='py-1.5 text-right'>
                  <button className='text-[12px] text-[#b45353] hover:underline' onClick={() => setAddedRules(prev => prev.filter((_, j) => j !== i))}>
                    {t('setting_undo')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className='mt-3 flex flex-wrap items-center gap-2'>
          <select value={newTool} onChange={e => setNewTool(e.target.value)} className='h-8 rounded-lg border border-[#e6e6e2] px-2 text-[12.5px] dark:border-[#33353b] dark:bg-[#17181c]'>
            {TOOL_OPTIONS.map(t => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <input
            value={newPattern}
            onChange={e => setNewPattern(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') addRule();
            }}
            placeholder={t('setting_pattern_ph')}
            className='h-8 flex-1 rounded-lg border border-[#e6e6e2] px-2 font-mono text-[12.5px] dark:border-[#33353b] dark:bg-[#17181c]'
          />
          <select value={newTier} onChange={e => setNewTier(e.target.value)} className='h-8 rounded-lg border border-[#e6e6e2] px-2 text-[12.5px] dark:border-[#33353b] dark:bg-[#17181c]'>
            {['confirm', 'deny', 'auto'].map(tier => (
              <option key={tier}>{tier}</option>
            ))}
          </select>
          <button
            className='h-8 rounded-lg bg-[#1c1c1a] px-3 text-[12.5px] text-white disabled:cursor-not-allowed disabled:opacity-40 dark:bg-white dark:text-black'
            disabled={!newPattern.trim()}
            title={!newPattern.trim() ? t('setting_pattern_required') : undefined}
            onClick={addRule}
          >
            {t('setting_add_rule')}
          </button>
        </div>
        {!newPattern.trim() && (
          <div className='mt-1.5 text-[12px] text-[#8b8b84]'>{t('setting_pattern_required')}</div>
        )}

        <div className='mt-4 border-t border-dashed border-[#e6e6e2] pt-3 dark:border-[#33353b]'>
          <div className={label}>{t('setting_playground')}</div>
          <div className='mt-2 flex gap-2'>
            <select value={pgTool} onChange={e => setPgTool(e.target.value)} className='h-8 rounded-lg border border-[#e6e6e2] px-2 text-[12.5px] dark:border-[#33353b] dark:bg-[#17181c]'>
              {TOOL_OPTIONS.map(t => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <input
              value={pgText}
              onChange={e => setPgText(e.target.value)}
              placeholder={t('setting_pg_ph')}
              className='h-8 flex-1 rounded-lg border border-[#e6e6e2] px-2 font-mono text-[12.5px] dark:border-[#33353b] dark:bg-[#17181c]'
            />
            <button className='h-8 rounded-lg border border-[#e6e6e2] px-3 text-[12.5px] text-[#5c5c55] dark:border-[#33353b]' onClick={runPlayground}>
              {t('setting_pg_run')}
            </button>
          </div>
          {pgResult && (
            <div className='mt-2 rounded-lg bg-[#f6f6f2] p-3 text-[12.5px] dark:bg-[#17181c]'>
              <div className='font-semibold'>
                {t('setting_pg_verdict')}<span className={pgResult.verdict[0] === 'deny' ? 'text-[#dc2626]' : pgResult.verdict[0] === 'confirm' ? 'text-[#b45353]' : 'text-[#3f7a3f]'}>{pgResult.verdict[0]}</span>
                <span className='ml-2 font-mono text-[#8b8b84]'>{pgResult.verdict[1]}</span>
              </div>
              <ul className='mt-1 space-y-0.5'>
                {pgResult.trace.map((t, i) => (
                  <li key={i} className={`font-mono ${t.hit ? 'font-semibold text-[#1c1c1a] dark:text-[#e6e4df]' : 'text-[#b9b9b2]'}`}>
                    {t.hit ? '✓' : '·'} {t.rule_id}（{t.tier}）
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

      {/* whitelist */}
      <section className={card}>
        <div className={label}>{t('setting_whitelist')}</div>
        <div className='mt-2 flex gap-2'>
          <input
            value={wlConv}
            onChange={e => setWlConv(e.target.value)}
            placeholder={t('setting_wl_ph')}
            className='h-8 flex-1 rounded-lg border border-[#e6e6e2] px-2 font-mono text-[12.5px] dark:border-[#33353b] dark:bg-[#17181c]'
          />
          <button className='h-8 rounded-lg border border-[#e6e6e2] px-3 text-[12.5px] dark:border-[#33353b]' onClick={loadWhitelist}>
            {t('setting_wl_query')}
          </button>
        </div>
        <table className='mt-2 w-full text-[12.5px]'>
          <tbody>
            {wl.map(w => (
              <tr key={`${w.scope}-${w.signature}`} className='border-t border-[#f0f0ec] dark:border-[#2a2b30]'>
                <td className='py-1.5'>{w.scope}</td>
                <td className='py-1.5 font-mono'>{w.signature}</td>
                <td className='py-1.5 font-mono text-[#8b8b84]'>{w.conv_id ?? '-'}</td>
                <td className='py-1.5 text-right'>
                  <button
                    className='text-[12px] text-[#b45353] hover:underline'
                    onClick={async () => {
                      await fetch(`${API}/api/v1/chat/approval/whitelist/revoke`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ scope: w.scope, signature: w.signature, conv_id: w.conv_id }),
                      });
                      loadWhitelist();
                    }}
                  >
                    {t('setting_revoke')}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* params */}
      <section className={card}>
        <div className={label}>{t('setting_params')}</div>
        <div className='mt-2 flex flex-wrap items-center gap-4 text-[13px]'>
          <label className='flex items-center gap-2'>
            {t('setting_p_ttl')}
            <input
              type='number'
              value={ttl}
              onChange={e => setTtl(Number(e.target.value))}
              className='h-8 w-24 rounded-lg border border-[#e6e6e2] px-2 dark:border-[#33353b] dark:bg-[#17181c]'
            />
          </label>
          <label className='flex items-center gap-2'>
            {t('setting_p_intent')}
            <input type='checkbox' checked={intent} onChange={e => setIntent(e.target.checked)} />
          </label>
          <label className='flex items-center gap-2'>
            {t('setting_p_failsafe')}
            <select value={failSafe} onChange={e => setFailSafe(e.target.value)} className='h-8 rounded-lg border border-[#e6e6e2] px-2 dark:border-[#33353b] dark:bg-[#17181c]'>
              <option value='confirm'>confirm</option>
              <option value='auto'>auto</option>
            </select>
          </label>
        </div>
      </section>

      {/* save bar */}
      {dirty > 0 && (
        <div className='fixed bottom-4 left-1/2 z-50 flex -translate-x-1/2 items-center gap-3 rounded-xl border border-[#e6e6e2] bg-white px-4 py-2 shadow-[0_12px_40px_rgba(20,20,15,.18)] dark:border-[#33353b] dark:bg-[#1e1f24]'>
          <span className='text-[13px] text-[#5c5c55]'>{t('setting_dirty', { n: dirty })}</span>
          <button className='h-8 rounded-lg border border-[#e6e6e2] px-3 text-[13px] dark:border-[#33353b]' onClick={() => load()}>
            {t('setting_discard')}
          </button>
          <button className='h-8 rounded-lg bg-[#1c1c1a] px-4 text-[13px] text-white dark:bg-white dark:text-black' onClick={save}>
            {t('setting_save')}
          </button>
        </div>
      )}
    </div>
  );
}
