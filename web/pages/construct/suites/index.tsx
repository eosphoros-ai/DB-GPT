import { getSuiteDetail, getSuites, setSuiteEnabled, uninstallSuite } from '@/client/api/suite';
import ConstructLayout from '@/new-components/layout/Construct';
import SuiteReadme from '@/new-components/suites/SuiteReadme';
import { SuiteItem } from '@/types/suite';
import { getUserId } from '@/utils';
import { localizeSuite, suiteDisplayName } from '@/utils/suite-routing';
import {
  AppstoreAddOutlined,
  ArrowRightOutlined,
  InboxOutlined,
  MoreOutlined,
  SearchOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { Button, Dropdown, Input, Segmented, Switch, Tag, Tooltip, message, theme } from 'antd';
import { useRouter } from 'next/router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

type Seg = 'official' | 'enterprise' | 'installed' | 'market';

const SuitesPage = () => {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const { token } = theme.useToken();
  const [suitePackages, setSuites] = useState<SuiteItem[]>([]);
  const [seg, setSeg] = useState<Seg>('official');
  const [search, setSearch] = useState('');
  const [mineOnly, setMineOnly] = useState(false);
  const [detailPackage, setDetail] = useState<SuiteItem | null>(null);
  const suites = useMemo(
    () => suitePackages.map(suite => localizeSuite(suite, i18n.language)),
    [suitePackages, i18n.language],
  );
  const detail = detailPackage ? localizeSuite(detailPackage, i18n.language) : null;
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
  }, [refresh, i18n.language]);

  const groups = useMemo(() => {
    const match = (s: SuiteItem) => {
      if (!search.trim()) return true;
      const kw = search.trim().toLowerCase();
      return (
        s.name.toLowerCase().includes(kw) ||
        suiteDisplayName(s, i18n.language).toLowerCase().includes(kw) ||
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
  }, [suites, search, mineOnly, i18n.language]);

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
        message.error(`${t('suites_upload_fail')}: ${body?.detail || body?.err_msg || res.status}`);
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
          {t(`suites_scenario_${suite.scenario_id}`, { defaultValue: suite.scenario_id || '-' })}
        </Tag>
        <Tag style={{ fontSize: 10 }}>
          {t('suites_execution')}: {suite.execution || 'react'}
        </Tag>
        <span className='ml-auto' onClick={e => e.stopPropagation()}>
          <Switch size='small' checked={suite.status === 'enabled'} onChange={checked => toggle(suite, checked)} />
        </span>
      </div>
      <p className='mt-2 line-clamp-2 text-xs' style={{ color: token.colorTextSecondary }}>
        {suite.manifest_snapshot?.description || suite.display || suite.name}
      </p>
      <div className='mt-2 flex flex-wrap gap-1'>
        {(suite.manifest_snapshot?.skills || []).map(skill => (
          <Tag key={skill} style={{ fontSize: 10 }}>
            {suite.skill_details?.find(item => item.name === skill)?.display || skill}
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
      <div className='mx-auto w-full min-w-0 max-w-[1180px] px-6 py-6'>
        {detail ? (
          <div>
            <Button type='link' className='px-0' onClick={() => setDetail(null)}>
              {t('suites_back')}
            </Button>
            {/* Header: icon box + title + version/source pills + author, right controls */}
            <div className='mt-4 flex items-start gap-4'>
              <div
                className='flex h-16 w-16 flex-shrink-0 items-center justify-center rounded-2xl border text-[28px]'
                style={{ borderColor: token.colorBorderSecondary, background: token.colorBgContainer }}
              >
                {detail.icon || '🧩'}
              </div>
              <div className='min-w-0 flex-1'>
                <div className='flex flex-wrap items-center gap-2'>
                  <span className='text-[22px] font-extrabold leading-7'>
                    {suiteDisplayName(detail, i18n.language)}
                  </span>
                  <Tag color='green' className='rounded-full' style={{ marginInlineEnd: 0 }}>
                    v{detail.version}
                  </Tag>
                  <Tag
                    color={detail.source === 'official' ? 'blue' : 'gold'}
                    className='rounded-full'
                    style={{ marginInlineEnd: 0 }}
                  >
                    {detail.source === 'official' ? t('suites_seg_official') : t('suites_seg_enterprise')}
                  </Tag>
                </div>
                <div className='mt-1 text-[12px]' style={{ color: token.colorTextTertiary }}>
                  @{detail.user_name || 'DB-GPT'}
                </div>
              </div>
              <div className='flex flex-shrink-0 items-center gap-3 pt-3'>
                <span className='text-[13px]' style={{ color: token.colorTextSecondary }}>
                  {t('suites_enable_label')}
                </span>
                <Switch checked={detail.status === 'enabled'} onChange={c => toggle(detail, c)} />
                <Dropdown
                  trigger={['click']}
                  menu={{
                    items: [
                      {
                        key: 'uninstall',
                        danger: true,
                        label: t('suites_uninstall'),
                        onClick: () => doUninstall(detail.name),
                      },
                    ],
                  }}
                >
                  <Button icon={<MoreOutlined />} />
                </Dropdown>
              </div>
            </div>

            <p className='mt-5 text-[13px] leading-7' style={{ color: token.colorTextSecondary }}>
              {detail.manifest_snapshot?.description || ''}
            </p>

            <h3 className='mb-3 mt-7 text-[15px] font-bold'>
              {t('suites_cmds')} ({(detail.manifest_snapshot?.commands || []).length})
            </h3>
            {(detail.manifest_snapshot?.commands || []).map((cmd: any) => (
              <button
                type='button'
                key={cmd.name || cmd}
                disabled={detail.status !== 'enabled'}
                onClick={() => router.push({ pathname: '/', query: { suite: detail.name, suite_command: cmd.name } })}
                className='mb-2 flex w-full text-left cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 text-[13px] transition-colors hover:border-[#b7eb8f] disabled:cursor-not-allowed disabled:opacity-50'
                style={{ borderColor: token.colorBorderSecondary, background: token.colorBgContainer }}
              >
                <Tag color='green' className='font-mono' style={{ fontSize: 11.5, marginInlineEnd: 0 }}>
                  {cmd.display || cmd.name || cmd}
                </Tag>
                <span style={{ color: token.colorTextSecondary }}>{cmd.description || cmd.summary || ''}</span>
                <ArrowRightOutlined className='ml-auto' style={{ color: token.colorTextQuaternary }} />
              </button>
            ))}

            <h3 className='mb-3 mt-7 text-[15px] font-bold'>
              {t('suites_skills_section')} ({(detail.skill_details || []).length})
            </h3>
            <div
              className='overflow-hidden rounded-xl border'
              style={{ borderColor: token.colorBorderSecondary, background: token.colorBgContainer }}
            >
              {(detail.skill_details || []).map((sk, i) => (
                <div
                  key={sk.name}
                  className='px-5 py-4'
                  style={{ borderTop: i ? `1px solid ${token.colorBorderSecondary}` : undefined }}
                >
                  <div className='text-[14px] font-bold'>{sk.display || sk.name}</div>
                  <p className='mt-1 text-[12.5px] leading-6' style={{ color: token.colorTextTertiary }}>
                    {sk.description}
                  </p>
                </div>
              ))}
              {(detail.skill_details || []).length === 0 && (
                <div className='px-5 py-6 text-center text-[12px]' style={{ color: token.colorTextTertiary }}>
                  —
                </div>
              )}
            </div>

            <h3 className='mb-2 mt-7 text-[15px] font-bold'>{t('suites_manifest')}</h3>
            <div className='rounded-xl border p-4 text-[12px]' style={{ borderColor: token.colorBorderSecondary }}>
              <div className='flex justify-between py-1'>
                <span style={{ color: token.colorTextTertiary }}>{t('suites_execution')}</span>
                <span className='font-mono font-bold'>{detail.execution || 'react'}</span>
              </div>
              <div className='flex justify-between py-1'>
                <span style={{ color: token.colorTextTertiary }}>{t('suites_allowed_tools')}</span>
                <span className='font-mono'>{(detail.manifest_snapshot?.tools?.allow || []).join(', ')}</span>
              </div>
              <div className='flex justify-between py-1'>
                <span style={{ color: token.colorTextTertiary }}>{t('suites_approval_policy')}</span>
                <Tooltip title={t('suites_overrides_note')}>
                  <span className='font-mono'>{t('suites_overrides_note')}</span>
                </Tooltip>
              </div>
              <div className='flex justify-between py-1'>
                <span style={{ color: token.colorTextTertiary }}>{t('suites_context_defaults')}</span>
                <span className='font-mono'>{JSON.stringify(detail.manifest_snapshot?.context_defaults || {})}</span>
              </div>
            </div>

            <SuiteReadme label={t('suites_readme_label')}>{detail.readme || ''}</SuiteReadme>
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
              <Button type='primary' icon={<UploadOutlined />} loading={busy} onClick={() => fileRef.current?.click()}>
                {t('suites_add')}
              </Button>
              <Button type='primary' href='/?creation_mode=expert_suite'>
                {i18n.language.startsWith('en') ? 'Create with AI' : '智能创建'}
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
