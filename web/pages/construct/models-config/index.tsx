import {
  apiInterceptors,
  connectModelProvider,
  copilotAuthPoll,
  copilotAuthStart,
  createCustomProvider,
  disableProviderModel,
  disconnectModelProvider,
  enableProviderModel,
  getModelProviders,
  getProviderConfig,
} from '@/client/api';
import { renderModelIcon } from '@/components/chat/header/model-selector';
import { ProviderSpriteIcon } from '@/components/icons/provider-icons';
import ConstructLayout from '@/new-components/layout/Construct';
import { ModelProvider, ProviderConfig } from '@/types/model';
import { notifyModelsChanged } from '@/utils/events';
import { CopyOutlined, SearchOutlined } from '@ant-design/icons';
import { Button, Empty, Form, Input, Modal, Segmented, Spin, Switch, Tag, Tooltip, message } from 'antd';
import Image from 'next/image';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

const WORKER_TYPES = ['llm', 'text2vec', 'reranker'];

// Max model rows rendered before the "show all" button kicks in (gateway
// catalogs can list hundreds of models).
const MODEL_CAP = 50;

// Curated popular providers (reference: opencode's provider list).
// Labels/descriptions come from i18n keys `provider_label_*` / `provider_desc_*`.
// Non-listed providers are hidden for now.
const POPULAR_PROVIDERS: Array<{ id: string }> = [
  { id: 'proxy/openai' },
  { id: 'proxy/github_copilot' },
  { id: 'proxy/claude' },
  { id: 'proxy/gemini' },
  { id: 'proxy/xai' },
  { id: 'proxy/vercel' },
  { id: 'proxy/deepseek' },
  { id: 'proxy/zhipu' },
  { id: 'proxy/moonshot' },
  { id: 'proxy/tongyi' },
  { id: 'proxy/volcengine' },
  { id: 'proxy/minimax' },
  { id: 'proxy/baichuan' },
  { id: 'proxy/yi' },
  { id: 'proxy/spark' },
  { id: 'proxy/wenxin' },
  { id: 'proxy/orcarouter' },
  { id: 'proxy/siliconflow' },
  { id: 'proxy/litellm' },
  { id: 'proxy/groq' },
  { id: 'proxy/mistral' },
  { id: 'proxy/nvidia' },
  { id: 'proxy/aimlapi' },
  { id: 'proxy/burncloud' },
  { id: 'proxy/gitee' },
  { id: 'proxy/infiniai' },
  { id: 'proxy/ollama' },
];

const POPULAR_ORDER = new Map(POPULAR_PROVIDERS.map((p, i) => [p.id, i]));

function providerI18nKey(provider: string): string | null {
  if (!provider.startsWith('proxy/')) return null;
  return provider.split('/')[1];
}

function formatContextLength(n?: number | null): string {
  if (!n) return '—';
  return n >= 1000 ? `${Math.round(n / 1000)}K` : `${n}`;
}

function cleanDescription(desc?: string | null): string {
  if (!desc) return '';
  return desc.replace(/^##\s*/m, '').trim();
}

// Monochrome brand glyphs extracted from opencode's icon spritesheet
// (see components/icons/provider-icons.tsx). Preferred over raster assets.
const PROVIDER_SPRITE_IDS: Record<string, string> = {
  'proxy/openai': 'openai',
  'proxy/github_copilot': 'github-copilot',
  'proxy/claude': 'anthropic',
  'proxy/gemini': 'google',
  'proxy/xai': 'xai',
  'proxy/vercel': 'vercel',
  'proxy/deepseek': 'deepseek',
  'proxy/zhipu': 'zhipuai',
  'proxy/moonshot': 'moonshotai',
  'proxy/tongyi': 'alibaba',
  'proxy/minimax': 'minimax',
  'proxy/siliconflow': 'siliconflow',
  'proxy/groq': 'groq',
  'proxy/mistral': 'mistral',
  'proxy/nvidia': 'nvidia',
  'proxy/ollama': 'ollama-cloud',
};

// Raster assets for providers missing from the spritesheet.
const PROVIDER_ICONS: Record<string, string> = {
  'proxy/volcengine': '/models/volc.jpg',
  'proxy/yi': '/models/yi.svg',
  'proxy/baichuan': '/models/baichuan.png',
  'proxy/wenxin': '/models/ernie.png',
  'proxy/litellm': '/models/litellm.jpg',
  'proxy/orcarouter': '/models/orcarouter.png',
};

// Pastel backgrounds for providers without an icon asset (deterministic by id).
const AVATAR_BG = [
  'bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300',
  'bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300',
  'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
  'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
  'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300',
  'bg-pink-100 text-pink-700 dark:bg-pink-900/40 dark:text-pink-300',
];

function ProviderAvatar({ label, size = 24, seed = '' }: { label: string; size?: number; seed?: string }) {
  const hash = [...(seed || label)].reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  const bg = AVATAR_BG[hash % AVATAR_BG.length];
  return (
    <div
      className={`rounded-full inline-flex items-center justify-center font-semibold shrink-0 ${bg}`}
      style={{ width: size, height: size, fontSize: Math.max(10, size * 0.42) }}
    >
      {(label || '?').slice(0, 1).toUpperCase()}
    </div>
  );
}

function providerIcon(
  provider: string,
  fallbackModel: string | undefined,
  props: { width: number; height: number } | undefined,
  label: string,
) {
  const size = props?.width || 24;
  const spriteId = PROVIDER_SPRITE_IDS[provider];
  if (spriteId) {
    return <ProviderSpriteIcon id={spriteId} size={size} className='text-gray-700 dark:text-gray-200 shrink-0' />;
  }
  const src = PROVIDER_ICONS[provider];
  if (src) {
    return (
      <Image
        className='rounded-full border border-gray-200 object-contain bg-white inline-block'
        src={src}
        width={size}
        height={props?.height || size}
        alt={provider}
      />
    );
  }
  if (fallbackModel) {
    return renderModelIcon(fallbackModel, props);
  }
  return <ProviderAvatar label={label} seed={provider} size={size} />;
}

function ModelsConfig() {
  const { t } = useTranslation();
  const [workerType, setWorkerType] = useState<string>('llm');
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [configs, setConfigs] = useState<Record<string, ProviderConfig>>({});
  const [selected, setSelected] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [connectModalOpen, setConnectModalOpen] = useState(false);
  const [connectForm] = Form.useForm();
  const [customModalOpen, setCustomModalOpen] = useState(false);
  const [customForm] = Form.useForm();
  const [modelQuery, setModelQuery] = useState('');
  const [showAllModels, setShowAllModels] = useState(false);
  // GitHub Copilot OAuth device flow state (opencode-style login).
  const [copilotAuth, setCopilotAuth] = useState<{
    phase: 'idle' | 'starting' | 'pending' | 'error';
    userCode?: string;
    verificationUri?: string;
    deviceCode?: string;
    interval?: number;
  } | null>(null);
  const copilotCancelledRef = useRef(false);

  async function loadProviders(wt: string) {
    setLoading(true);
    const [, res] = await apiInterceptors(getModelProviders(wt));
    const list = res ?? [];
    setProviders(list);
    await loadConfigs(list);
    setLoading(false);
  }

  async function loadConfigs(list: ModelProvider[]) {
    const results = await Promise.all(
      list.map(async p => {
        const [, cfg] = await apiInterceptors(getProviderConfig(p.provider));
        return [p.provider, cfg] as const;
      }),
    );
    const map: Record<string, ProviderConfig> = {};
    results.forEach(([provider, cfg]) => {
      if (cfg) map[provider] = cfg;
    });
    setConfigs(map);
  }

  useEffect(() => {
    loadProviders(workerType);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workerType]);

  // Popular built-in providers first (curated order), then custom providers.
  const visibleProviders = useMemo(() => {
    return providers
      .filter(p => POPULAR_ORDER.has(p.provider) || p.provider.startsWith('custom/'))
      .sort((a, b) => {
        const ai = POPULAR_ORDER.get(a.provider);
        const bi = POPULAR_ORDER.get(b.provider);
        if (ai !== undefined && bi !== undefined) return ai - bi;
        if (ai !== undefined) return -1;
        if (bi !== undefined) return 1;
        return (a.name || '').localeCompare(b.name || '');
      })
      .map(p => {
        const key = providerI18nKey(p.provider);
        const label = key ? (t(`provider_label_${key}` as any) as string) : '';
        return { ...p, name: label || p.name };
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [providers, t]);

  useEffect(() => {
    if (selected && visibleProviders.some(p => p.provider === selected)) return;
    setSelected(visibleProviders[0]?.provider ?? '');
  }, [visibleProviders, selected]);

  const current = useMemo(() => visibleProviders.find(p => p.provider === selected), [visibleProviders, selected]);

  const isCopilot = current?.provider === 'proxy/github_copilot';

  // Reset the model search / pagination when switching provider.
  useEffect(() => {
    setShowAllModels(false);
    setModelQuery('');
  }, [selected]);

  const currentKey = current ? providerI18nKey(current.provider) : null;
  const currentHint = currentKey ? ((t(`provider_desc_${currentKey}` as any) as string) ?? '') : '';

  const filteredModels = useMemo(() => {
    const query = modelQuery.trim().toLowerCase();
    if (!current) return [];
    if (!query) return current.models;
    return current.models.filter(m => {
      const hay = `${m.model} ${m.label ?? ''} ${m.description ?? ''}`.toLowerCase();
      return hay.includes(query);
    });
  }, [current, modelQuery]);

  const visibleModels = useMemo(
    () => (showAllModels ? filteredModels : filteredModels.slice(0, MODEL_CAP)),
    [filteredModels, showAllModels],
  );

  function isConnected(provider: string) {
    return Boolean(configs[provider]?.connected);
  }

  function isEnabled(provider: string, model: string) {
    return (configs[provider]?.enabled_models ?? []).includes(model);
  }

  async function toggleModel(provider: string, model: string, enabled: boolean) {
    const prev = configs[provider]?.enabled_models ?? [];
    const next = enabled ? [...prev, model] : prev.filter(m => m !== model);
    // optimistic update
    setConfigs(cfg => ({
      ...cfg,
      [provider]: {
        ...cfg[provider],
        provider,
        enabled_models: next,
        connected: cfg[provider]?.connected ?? false,
      } as ProviderConfig,
    }));
    // Actually start/stop the proxy worker so the model becomes usable.
    const [, , data] = await apiInterceptors(
      enabled ? enableProviderModel(provider, model) : disableProviderModel(provider, model),
    );
    if (data?.success) {
      message.success(enabled ? t('enabled') : t('disabled'));
      notifyModelsChanged();
    } else {
      // revert on failure
      setConfigs(cfg => ({
        ...cfg,
        [provider]: {
          ...cfg[provider],
          provider,
          enabled_models: prev,
          connected: cfg[provider]?.connected ?? false,
        } as ProviderConfig,
      }));
    }
  }

  async function connectProvider(values: { api_key?: string; api_base?: string }) {
    if (!current) return;
    const [, res] = await apiInterceptors(
      connectModelProvider(current.provider, { api_key: values.api_key, api_base: values.api_base }),
    );
    if (res) {
      setConfigs(cfg => ({
        ...cfg,
        [current.provider]: {
          ...cfg[current.provider],
          provider: current.provider,
          connected: Boolean(res.connected),
          api_base: values.api_base ?? cfg[current.provider]?.api_base ?? null,
          enabled_models: res.enabled_models ?? [],
        } as ProviderConfig,
      }));
      setConnectModalOpen(false);
      connectForm.resetFields();
      message.success(t('connected'));
      notifyModelsChanged();
    }
  }

  // Start the OAuth device flow when the Copilot connect modal opens; poll
  // until the user authorizes at github.com/login/device (or it expires).
  useEffect(() => {
    if (!connectModalOpen || !isCopilot) return;
    copilotCancelledRef.current = false;
    let cancelled = false;
    (async () => {
      setCopilotAuth({ phase: 'starting' });
      const [, res] = await apiInterceptors(copilotAuthStart());
      if (cancelled) return;
      if (!res?.device_code) {
        setCopilotAuth({ phase: 'error' });
        return;
      }
      setCopilotAuth({
        phase: 'pending',
        userCode: res.user_code,
        verificationUri: res.verification_uri,
        deviceCode: res.device_code,
        interval: res.interval,
      });
      const deadline = Date.now() + 15 * 60 * 1000;
      while (!cancelled && Date.now() < deadline) {
        await new Promise(r => setTimeout(r, Math.max(1, (res.interval ?? 5) + 3) * 1000));
        if (cancelled) return;
        const [, poll] = await apiInterceptors(copilotAuthPoll(res.device_code), ['*']);
        if (cancelled) return;
        if (poll?.status === 'success') {
          const enabled = poll.enabled_models ?? [];
          setConfigs(cfg => ({
            ...cfg,
            'proxy/github_copilot': {
              ...(cfg['proxy/github_copilot'] ?? {}),
              provider: 'proxy/github_copilot',
              connected: true,
              api_base: cfg['proxy/github_copilot']?.api_base ?? null,
              enabled_models: enabled,
            } as ProviderConfig,
          }));
          message.success(t('connected'));
          notifyModelsChanged();
          setConnectModalOpen(false);
          return;
        }
        if (poll?.status === 'pending' || poll?.status === 'slow_down') continue;
        setCopilotAuth({ phase: 'error' });
        return;
      }
      if (!cancelled) setCopilotAuth(a => (a && a.phase === 'pending' ? { phase: 'error' } : a));
    })();
    return () => {
      cancelled = true;
      copilotCancelledRef.current = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connectModalOpen, isCopilot]);

  async function disconnectProvider() {
    if (!current) return;
    const [, , data] = await apiInterceptors(disconnectModelProvider(current.provider));
    if (data?.success) {
      setConfigs(cfg => ({
        ...cfg,
        [current.provider]: {
          provider: current.provider,
          connected: false,
          api_base: null,
          enabled_models: [],
        },
      }));
      message.success(t('disconnected'));
      notifyModelsChanged();
      await loadProviders(workerType);
    }
  }

  async function createCustomProviderHandler(values: {
    label?: string;
    api_base?: string;
    api_key?: string;
    models?: string;
  }) {
    const models = (values.models ?? '')
      .split(/[\n,]/)
      .map(m => m.trim())
      .filter(Boolean);
    const [, , data] = await apiInterceptors(
      createCustomProvider({
        label: values.label ?? '',
        api_base: values.api_base ?? '',
        api_key: values.api_key ?? '',
        models,
      }),
    );
    if (data?.success) {
      setCustomModalOpen(false);
      customForm.resetFields();
      message.success(t('add_provider_success'));
      notifyModelsChanged();
      await loadProviders(workerType);
    }
  }

  return (
    <ConstructLayout className='models-config-tabs'>
      <div className='p-6 flex flex-col gap-4 h-full min-h-0'>
        <div className='flex items-center justify-between'>
          <Segmented
            value={workerType}
            options={WORKER_TYPES.map(w => ({ label: w, value: w }))}
            onChange={val => setWorkerType(val as string)}
          />
          <Button onClick={() => setCustomModalOpen(true)}>{t('add_custom_provider')}</Button>
        </div>

        <div className='flex gap-4 flex-1 min-h-0'>
          {/* Provider list */}
          <div className='w-72 shrink-0 flex flex-col rounded-2xl border border-black/5 dark:border-white/10 p-2 min-h-0'>
            <div className='px-2 py-1 text-xs text-gray-400'>{t('model_providers')}</div>
            <div className='flex-1 overflow-y-auto min-h-0'>
              <Spin spinning={loading}>
                {visibleProviders.length === 0 && !loading ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('no_data')} />
                ) : (
                  <div className='flex flex-col gap-1'>
                    {visibleProviders.map(p => (
                      <div
                        key={p.provider}
                        onClick={() => setSelected(p.provider)}
                        className={`flex items-center gap-3 px-2 py-2 rounded-xl cursor-pointer transition-colors ${
                          p.provider === selected
                            ? 'bg-blue-50 dark:bg-blue-900/20'
                            : 'hover:bg-black/5 dark:hover:bg-white/5'
                        }`}
                      >
                        {providerIcon(p.provider, p.models[0]?.model, undefined, p.name)}
                        <div className='flex-1 min-w-0'>
                          <div className='truncate text-sm'>{p.name}</div>
                          <div className='text-xs text-gray-400 truncate'>{p.provider}</div>
                        </div>
                        {isConnected(p.provider) && (
                          <Tag color='green' className='m-0'>
                            {t('connected')}
                          </Tag>
                        )}
                        <span className='text-xs text-gray-400'>{p.models.length}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Spin>
            </div>
          </div>

          {/* Provider detail */}
          <div className='flex-1 min-w-0 overflow-y-auto rounded-2xl border border-black/5 dark:border-white/10 p-4'>
            {!current ? (
              <div className='h-full flex items-center justify-center'>
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={t('no_provider_selected')} />
              </div>
            ) : (
              <div className='flex flex-col gap-4'>
                <div className='flex items-center gap-3 flex-wrap'>
                  {providerIcon(
                    current.provider,
                    current.models[0]?.model,
                    {
                      width: 32,
                      height: 32,
                    },
                    current.name,
                  )}
                  <h2 className='text-lg font-semibold'>{current.name}</h2>
                  <Tag color={current.proxy ? 'blue' : 'default'} className='m-0'>
                    {current.proxy ? t('proxy_provider') : t('local_provider')}
                  </Tag>
                  <div className='flex-1' />
                  {isConnected(current.provider) ? (
                    <div className='flex items-center gap-2'>
                      <Tag color='green' className='m-0'>
                        {t('connected')}
                      </Tag>
                      <Button size='small' onClick={() => setConnectModalOpen(true)}>
                        {t('reconnect')}
                      </Button>
                      <Button size='small' danger onClick={disconnectProvider}>
                        {t('disconnect')}
                      </Button>
                    </div>
                  ) : (
                    <Button
                      className='border-none text-white bg-button-gradient'
                      onClick={() => setConnectModalOpen(true)}
                    >
                      {t('connect')}
                    </Button>
                  )}
                </div>

                {currentHint && <div className='text-xs text-gray-400'>{currentHint}</div>}

                <div className='flex items-center gap-2'>
                  <Input
                    allowClear
                    size='small'
                    prefix={<SearchOutlined className='text-gray-400' />}
                    placeholder={t('search_models')}
                    value={modelQuery}
                    onChange={e => setModelQuery(e.target.value)}
                    className='max-w-xs'
                  />
                  {modelQuery && (
                    <span className='text-xs text-gray-400'>
                      {filteredModels.length} / {current.models.length}
                    </span>
                  )}
                </div>

                <div className='flex flex-col gap-1'>
                  {visibleModels.map(m => {
                    const checked = isEnabled(current.provider, m.model);
                    return (
                      <div
                        key={m.model}
                        className='flex items-center gap-3 px-3 py-2 rounded-xl hover:bg-black/5 dark:hover:bg-white/5'
                      >
                        {renderModelIcon(m.model)}
                        <Tooltip title={cleanDescription(m.description)} placement='topLeft'>
                          <span className='flex-1 truncate text-sm'>{m.label}</span>
                        </Tooltip>
                        {m.function_calling && (
                          <Tag color='geekblue' className='m-0'>
                            {t('function_calling')}
                          </Tag>
                        )}
                        <span className='text-xs text-gray-400 w-16 text-right' title={t('context_length')}>
                          {formatContextLength(m.context_length)}
                        </span>
                        <Switch
                          size='small'
                          checked={checked}
                          onChange={val => toggleModel(current.provider, m.model, val)}
                        />
                      </div>
                    );
                  })}
                  {visibleModels.length === 0 && (
                    <div className='text-xs text-gray-400 py-4 text-center'>{t('no_data')}</div>
                  )}
                  {filteredModels.length > MODEL_CAP && (
                    <Button type='text' size='small' onClick={() => setShowAllModels(v => !v)} className='mt-1'>
                      {showAllModels ? t('show_less_models') : t('show_all_models', { count: filteredModels.length })}
                    </Button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      <Modal
        width={480}
        open={connectModalOpen}
        title={`${t('connect')} — ${current?.name ?? ''}`}
        onCancel={() => {
          setConnectModalOpen(false);
          setCopilotAuth(null);
        }}
        footer={null}
        destroyOnClose
      >
        {currentHint && <div className='mb-3 text-xs text-gray-400'>{currentHint}</div>}
        {isCopilot ? (
          /* GitHub Copilot: OAuth device flow only — GitHub rejects PATs. */
          <div className='flex flex-col gap-4'>
            <div className='text-sm leading-6'>
              {copilotAuth?.verificationUri ? (
                <>
                  {t('copilot_visit_prompt')}
                  <a
                    href={copilotAuth.verificationUri}
                    target='_blank'
                    rel='noreferrer'
                    className='text-blue-500 underline mx-1'
                  >
                    {copilotAuth.verificationUri}
                  </a>
                  {t('copilot_visit_prompt_suffix')}
                </>
              ) : (
                t('copilot_visit_prompt')
              )}
            </div>
            <div>
              <div className='text-xs text-gray-400 mb-1'>{t('copilot_code_label')}</div>
              <div className='flex items-center gap-2'>
                <Input
                  readOnly
                  value={copilotAuth?.userCode ?? ''}
                  placeholder='XXXX-XXXX'
                  className='font-mono text-base'
                />
                <Button
                  icon={<CopyOutlined />}
                  disabled={!copilotAuth?.userCode}
                  onClick={() => {
                    navigator.clipboard.writeText(copilotAuth?.userCode ?? '');
                    message.success(t('copied_code'));
                  }}
                />
              </div>
            </div>
            <div className='flex items-center gap-2 text-sm text-gray-500 min-h-6'>
              {copilotAuth?.phase === 'error' ? (
                <span className='text-red-500'>{t('copilot_auth_failed')}</span>
              ) : (
                <>
                  {(copilotAuth?.phase === 'pending' || copilotAuth?.phase === 'starting') && <Spin size='small' />}
                  {t('waiting_authorization')}
                </>
              )}
            </div>
          </div>
        ) : (
          <Form form={connectForm} layout='vertical' onFinish={connectProvider}>
            <Form.Item
              name='api_key'
              label={t('model_api_key')}
              rules={[
                {
                  required: current?.provider !== 'proxy/ollama',
                  message: t('model_api_key'),
                },
              ]}
            >
              <Input.Password
                autoComplete='new-password'
                placeholder={
                  current?.provider === 'proxy/wenxin'
                    ? t('wenxin_key_hint')
                    : current?.provider === 'proxy/ollama'
                      ? 'not required'
                      : 'sk-...'
                }
              />
            </Form.Item>
            <Form.Item name='api_base' label={t('api_base_optional')}>
              <Input placeholder='https://...' />
            </Form.Item>
            <div className='flex justify-end gap-2'>
              <Button onClick={() => setConnectModalOpen(false)}>{t('cancel')}</Button>
              <Button type='primary' htmlType='submit'>
                {t('connect')}
              </Button>
            </div>
          </Form>
        )}
      </Modal>

      <Modal
        width={520}
        open={customModalOpen}
        title={t('add_custom_provider')}
        onCancel={() => setCustomModalOpen(false)}
        footer={null}
        destroyOnClose
      >
        <Form form={customForm} layout='vertical' onFinish={createCustomProviderHandler}>
          <Form.Item name='label' label={t('provider_name')} rules={[{ required: true, message: t('provider_name') }]}>
            <Input placeholder='My Gateway' />
          </Form.Item>
          <Form.Item name='api_base' label={t('api_base')} rules={[{ required: true, message: t('api_base') }]}>
            <Input placeholder='https://api.example.com/v1' />
          </Form.Item>
          <Form.Item
            name='api_key'
            label={t('model_api_key')}
            rules={[{ required: true, message: t('model_api_key') }]}
          >
            <Input.Password autoComplete='new-password' placeholder='sk-...' />
          </Form.Item>
          <Form.Item name='models' label={t('model_list')} rules={[{ required: true, message: t('model_list') }]}>
            <Input.TextArea rows={3} placeholder='gpt-4o, gpt-4o-mini' />
          </Form.Item>
          <div className='flex justify-end gap-2'>
            <Button onClick={() => setCustomModalOpen(false)}>{t('cancel')}</Button>
            <Button type='primary' htmlType='submit'>
              {t('submit')}
            </Button>
          </div>
        </Form>
      </Modal>
    </ConstructLayout>
  );
}

export default ModelsConfig;
