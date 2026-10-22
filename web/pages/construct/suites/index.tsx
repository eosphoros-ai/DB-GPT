import { getSuiteDetail, getSuites, setSuiteEnabled, uninstallSuite } from '@/client/api/suite';
import MarkDownContext from '@/new-components/common/MarkdownContext';
import ConstructLayout from '@/new-components/layout/Construct';
import { SuiteItem } from '@/types/suite';
import { getUserId } from '@/utils';
import { suiteDisplayName } from '@/utils/suite-routing';
import {
  AppstoreAddOutlined,
  InboxOutlined,
  SearchOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { Button, Input, Popconfirm, Segmented, Switch, Tag, Tooltip, message, theme } from 'antd';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

type Seg = 'official' | 'enterprise' | 'installed' | 'market';

const SuitesPage = () => {
  const { t, i18n } = useTranslation();
  const { token } = theme.useToken();
  const [suites, setSuites] = useState<SuiteItem[]>([]);
  const [seg, setSeg] = useState<Seg>('official');
  const [search, setSearch] = useState('');
  const [mineOnly, setMineOnly] = useState(false);
  const [detail, setDetail] = useState<SuiteItem | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    try {
      const list = await getSuites();
      if (Array.isArray(list)) setSuites(list);
    } catch {
      /* registry unreachable: keep last list */
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const groups = useMemo(() => {
    const match = (s: SuiteItem) => {
      if (!search.trim()) return true;
      const kw = search.trim().toLowerCase();
      return (
        s.name.toLowerCase().includes(kw) ||
        (s.display || '').toLowerCase().includes(kw) ||
        (s.manifest_snapshot?.description || '').toLowerCase().includes(kw)
      );
    };
    const mine = (s: SuiteItem) => !mineOnly || s.user_name === getUserId();
    const all = suites.filter(s => match(s) && mine(s));
    return {
      official: all.filter(s => s.source === 'official'),
      enterprise: all.filter(s => s.source === 'enterprise'),
      installed: all.filter(s => s.status === 'enabled'),
      market: [] as SuiteItem[],
    };
  }, [suites, search, mineOnly]);

  const openDetail = async (name: string) => {
    try {
      const row = await getSuiteDetail(name);
      if (row) setDetail(row);
    } catch {
      /* ignore: detail stays closed */
    }
  };

  const toggle = async (suite: SuiteItem, enabled: boolean) => {
    try {
      await setSuiteEnabled(suite.name, enabled);
    } catch (err: any) {
      message.error(`${t('suites_upload_fail')}: ${err?.message ?? err}`);
      return;
    }
    await refresh();
    if (detail?.name === suite.name) openDetail(suite.name);
  };

  const onUpload = async (file: File) => {
    setBusy(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/suites/upload`, {
        method: 'POST',
        body: form,
      });
      const body = await res.json();
      if (res.ok && body?.success) {
        message.success(t('suites_upload_ok'));
        await refresh();
      } else {
        message.error(`${t('suites_upload_fail')}: ${body?.err_msg || res.status}`);
      }
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const doUninstall = async (name: string) => {
    try {
      await uninstallSuite(name);
    } catch (err: any) {
      message.error(`${t('suites_upload_fail')}: ${err?.message ?? err}`);
      return;
    }
    setDetail(null);
    await refresh();
  };

  const card = (suite: SuiteItem) => (
    <div
      key={suite.name}
      onClick={() => openDetail(suite.name)}
      className='cursor-pointer rounded-xl border p-4 transition-all hover:-translate-y-0.5 hover:shadow-lg'
      style={{ borderColor: token.colorBorderSecondary, background: token.colorBgContainer }}
    >
      <div className='flex items-center gap-2'>
        <span className='text-[18px]'>{suite.icon || '🧩'}</span>
        <span className='text-[14px] font-bold'>{suiteDisplayName(suite, i18n.language)}</span>
        <Tag className='ml-1' style={{ fontSize: 10 }}>
          scenario:{suite.scenario_id || '-'}
        </Tag>
        <Tag style={{ fontSize: 10 }}>exec:{suite.execution || 'react'}</Tag>
        <span className='ml-auto' onClick={e => e.stopPropagation()}>
          <Switch
            size='small'
            checked={suite.status === 'enabled'}
            onChange={checked => toggle(suite, checked)}
          />
        </span>
      </div>
      <p className='mt-2 line-clamp-2 text-xs' style={{ color: token.colorTextSecondary }}>
        {suite.manifest_snapshot?.description || suite.display || suite.name}
      </p>
      <div className='mt-2 flex flex-wrap gap-1'>
        {(suite.manifest_snapshot?.skills || []).map(skill => (
          <Tag key={skill} style={{ fontSize: 10 }}>
            {skill}
          </Tag>
        ))}
      </div>
      <div className='mt-3 flex items-center gap-2 text-[11px]' style={{ color: token.colorTextTertiary }}>
        <span>{t('suites_skills_count', { count: suite.manifest_snapshot?.skills?.length ?? 0 })}</span>
        <span>·</span>
        <span>{suite.status === 'enabled' ? t('suites_enabled') : t('suites_disabled')}</span>
        <span className='ml-auto font-mono'>v{suite.version}</span>
      </div>
    </div>
  );

  const list = groups[seg];

  return (
    <ConstructLayout>
      <div className='mx-auto max-w-[1180px] px-6 py-6'>
        {detail ? (
          <div>
            <Button type='link' className='px-0' onClick={() => setDetail(null)}>
              {t('suites_back')}
            </Button>
            <div className='mt-2 flex items-center gap-3'>
              <span className='text-[26px]'>{detail.icon || '🧩'}</span>
              <div>
                <div className='font-mono text-[17px] font-extrabold'>{detail.name}</div>
                <div className='text-[11px]' style={{ color: token.colorTextTertiary }}>
                  @{detail.user_name || 'DB-GPT'}
                </div>
              </div>
              <Tag color='green'>v{detail.version}</Tag>
              <Tag color={detail.source === 'official' ? 'blue' : 'gold'}>
                {detail.source === 'official' ? t('suites_seg_official') : t('suites_seg_enterprise')}
              </Tag>
              <div className='ml-auto flex items-center gap-2'>
                <Switch
                  checked={detail.status === 'enabled'}
                  onChange={checked => toggle(detail, checked)}
                />
                <Popconfirm
                  title={t('suites_uninstall_confirm', { name: detail.name })}
                  onConfirm={() => doUninstall(detail.name)}
                >
                  <Button danger size='small'>
                    {t('suites_uninstall')}
                  </Button>
                </Popconfirm>
              </div>
            </div>
            <div className='mt-4 text-[12.8px] leading-6' style={{ color: token.colorTextSecondary }}>
              <MarkDownContext>
                {detail.readme || detail.manifest_snapshot?.description || ''}
              </MarkDownContext>
            </div>
            <h3 className='mb-2 mt-5 text-[14px] font-bold'>
              {t('suites_cmds')}（{(detail.manifest_snapshot?.commands || []).length}）
            </h3>
            {(detail.manifest_snapshot?.commands || []).map((cmd: any) => (
              <div
                key={cmd.name || cmd}
                className='mb-2 flex items-center gap-3 rounded-lg border px-3 py-2 text-[12.4px]'
                style={{ borderColor: token.colorBorderSecondary, background: token.colorBgContainer }}
              >
                <Tag color='green' className='font-mono' style={{ fontSize: 11 }}>
                  {cmd.name || cmd}
                </Tag>
                <span style={{ color: token.colorTextSecondary }}>{cmd.description || ''}</span>
              </div>
            ))}
            <h3 className='mb-2 mt-5 text-[14px] font-bold'>{t('suites_manifest')}</h3>
            <div className='rounded-lg border p-3 text-[12px]' style={{ borderColor: token.colorBorderSecondary }}>
              <div className='flex justify-between py-1'>
                <span style={{ color: token.colorTextTertiary }}>execution</span>
                <span className='font-mono font-bold'>{detail.execution || 'react'}</span>
              </div>
              <div className='flex justify-between py-1'>
                <span style={{ color: token.colorTextTertiary }}>tools.allow</span>
                <span className='font-mono'>{(detail.manifest_snapshot?.tools?.allow || []).join(', ')}</span>
              </div>
              <div className='flex justify-between py-1'>
                <span style={{ color: token.colorTextTertiary }}>approval_overrides</span>
                <Tooltip title={t('suites_overrides_note')}>
                  <span className='font-mono'>{t('suites_overrides_note')}</span>
                </Tooltip>
              </div>
              <div className='flex justify-between py-1'>
                <span style={{ color: token.colorTextTertiary }}>context_defaults</span>
                <span className='font-mono'>
                  {JSON.stringify(detail.manifest_snapshot?.context_defaults || {})}
                </span>
              </div>
            </div>
          </div>
        ) : (
          <>
            <h2 className='flex items-center gap-2 text-[19px] font-extrabold'>
              <AppstoreAddOutlined /> {t('suites')}
            </h2>
            <p className='mb-4 mt-1 text-[12.5px]' style={{ color: token.colorTextSecondary }}>
              {t('suites_sub')}
            </p>
            <div className='mb-3 flex items-center gap-3'>
              <Input
                allowClear
                prefix={<SearchOutlined style={{ color: token.colorTextTertiary }} />}
                placeholder={t('suites_search')}
                style={{ maxWidth: 320 }}
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              <Button
                type='primary'
                icon={<UploadOutlined />}
                loading={busy}
                onClick={() => fileRef.current?.click()}
              >
                {t('suites_add')}
              </Button>
              <input
                ref={fileRef}
                type='file'
                accept='.zip'
                className='hidden'
                onChange={e => e.target.files?.[0] && onUpload(e.target.files[0])}
              />
              <Button type={mineOnly ? 'primary' : 'text'} ghost={mineOnly} onClick={() => setMineOnly(v => !v)}>
                {t('suites_my_published')}
              </Button>
            </div>
            <Segmented
              className='mb-4'
              value={seg}
              onChange={v => setSeg(v as Seg)}
              options={[
                { label: `${t('suites_seg_official')} ${groups.official.length}`, value: 'official' },
                { label: `${t('suites_seg_enterprise')} ${groups.enterprise.length}`, value: 'enterprise' },
                { label: `${t('suites_seg_installed')} ${groups.installed.length}`, value: 'installed' },
                { label: t('suites_seg_market'), value: 'market' },
              ]}
            />
            {seg === 'market' ? (
              <div
                className='rounded-xl border border-dashed p-8 text-center text-[12.5px]'
                style={{ borderColor: token.colorBorder, color: token.colorTextTertiary }}
              >
                <InboxOutlined className='mb-2 text-[22px]' />
                <div>{t('suites_market_empty')}</div>
              </div>
            ) : (
              <div className='grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3'>
                {list.map(card)}
                {list.length === 0 && (
                  <div
                    className='col-span-full rounded-xl border border-dashed p-8 text-center text-[12.5px]'
                    style={{ borderColor: token.colorBorder, color: token.colorTextTertiary }}
                  >
                    <InboxOutlined className='mb-2 text-[22px]' />
                    {t('suites_market_empty')}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </ConstructLayout>
  );
};

export default SuitesPage;
