import { getSuiteDetail, getSuites, setSuiteEnabled, uninstallSuite } from '@/client/api/suite';
import ConstructLayout from '@/new-components/layout/Construct';
import styles from '@/new-components/suites/PluginCenter.module.css';
import {
  artifactPresentation,
  getBuiltinPresentation,
  getSuiteCategory,
  matchesSuiteSource,
  SuiteCategory,
  SuiteSourceFilter,
} from '@/new-components/suites/presentation';
import SuiteIcon from '@/new-components/suites/SuiteIcon';
import SuiteReadme from '@/new-components/suites/SuiteReadme';
import type { SuiteCommand, SuiteItem } from '@/types/suite';
import { getUserId } from '@/utils';
import { localizeSuite, suiteDisplayName } from '@/utils/suite-routing';
import {
  ArrowRightOutlined,
  BookOutlined,
  CheckCircleFilled,
  InboxOutlined,
  MoreOutlined,
  PlusOutlined,
  SearchOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { Alert, Button, Drawer, Dropdown, Input, message, Modal, Spin, Switch, Tabs, theme } from 'antd';
import { useRouter } from 'next/router';
import { CSSProperties, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

const categories: SuiteCategory[] = ['all', 'query', 'analysis', 'financial', 'metadata', 'ops', 'other'];
const sources: SuiteSourceFilter[] = ['official', 'enterprise', 'installed', 'market'];

export default function SuitesPage() {
  const router = useRouter();
  const { t, i18n } = useTranslation();
  const { token } = theme.useToken();
  const [modal, contextHolder] = Modal.useModal();
  const [suitePackages, setSuites] = useState<SuiteItem[]>([]);
  const [source, setSource] = useState<SuiteSourceFilter>('official');
  const [category, setCategory] = useState<SuiteCategory>('all');
  const [search, setSearch] = useState('');
  const [manage, setManage] = useState(false);
  const [mineOnly, setMineOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [pending, setPending] = useState<Record<string, boolean>>({});
  const [detailName, setDetailName] = useState<string | null>(null);
  const [detailPackage, setDetail] = useState<SuiteItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState(false);
  const [detailTab, setDetailTab] = useState('overview');
  const fileRef = useRef<HTMLInputElement>(null);
  const listRequest = useRef(0);
  const detailRequest = useRef(0);
  const suites = useMemo(
    () => suitePackages.map(suite => localizeSuite(suite, i18n.language)),
    [suitePackages, i18n.language],
  );
  const detail = detailPackage ? localizeSuite(detailPackage, i18n.language) : null;
  const colors = {
    '--suite-bg': token.colorBgContainer,
    '--suite-text': token.colorText,
    '--suite-muted': token.colorTextSecondary,
    '--suite-border': token.colorBorderSecondary,
    '--suite-hover': token.colorFillQuaternary,
    '--suite-icon-bg': token.colorFillSecondary,
    '--suite-primary': token.colorPrimary,
    '--suite-success': token.colorSuccess,
  } as CSSProperties;

  const refresh = useCallback(async () => {
    const request = ++listRequest.current;
    setLoading(true);
    setListError(false);
    try {
      const list = await getSuites();
      if (request === listRequest.current) setSuites(list);
    } catch {
      if (request === listRequest.current) setListError(true);
    } finally {
      if (request === listRequest.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const lists = listRequest;
    const details = detailRequest;
    refresh();
    return () => {
      lists.current++;
      details.current++;
    };
  }, [refresh]);

  const title = (suite: SuiteItem) => {
    const builtin = getBuiltinPresentation(suite);
    return builtin ? t(builtin.title) : suiteDisplayName(suite, i18n.language);
  };
  const description = (suite: SuiteItem) => {
    const builtin = getBuiltinPresentation(suite);
    return builtin ? t(builtin.description) : suite.manifest_snapshot?.description || '';
  };
  const statusLabel = (suite: SuiteItem) =>
    suite.status === 'enabled'
      ? t('suites_enabled')
      : suite.status === 'installed'
        ? t('plugins_installed_state')
        : suite.status === 'disabled'
          ? t('suites_disabled')
          : suite.status;
  const sourceLabel = (value: SuiteSourceFilter) =>
    value === 'official' ? t('plugins_official') : t(`suites_seg_${value}`);
  const filtered = suites.filter(suite => {
    if (!matchesSuiteSource(suite, source)) return false;
    if (category !== 'all' && getSuiteCategory(suite) !== category) return false;
    if (mineOnly && suite.user_name !== getUserId()) return false;
    const text = [
      suite.name,
      suiteDisplayName(suite, i18n.language),
      title(suite),
      suite.manifest_snapshot?.description,
      ...(suite.skill_details || []).flatMap(skill => [skill.display, skill.description]),
      ...(suite.manifest_snapshot?.commands || []).flatMap(command => [command.display, command.description]),
    ].join(' ');
    return text.toLowerCase().includes(search.trim().toLowerCase());
  });
  const counts = Object.fromEntries(
    sources.map(value => [value, suites.filter(s => matchesSuiteSource(s, value)).length]),
  );

  const openDetail = async (name: string, tab = 'overview') => {
    const request = ++detailRequest.current;
    setDetailName(name);
    setDetailTab(tab);
    setDetail(null);
    setDetailLoading(true);
    setDetailError(false);
    try {
      const row = await getSuiteDetail(name);
      if (!row) throw new Error('Plugin not found');
      if (request === detailRequest.current) setDetail(row);
    } catch {
      if (request === detailRequest.current) setDetailError(true);
    } finally {
      if (request === detailRequest.current) setDetailLoading(false);
    }
  };

  const closeDetail = () => {
    detailRequest.current++;
    setDetailName(null);
  };
  const runCommand = (suite: SuiteItem, command: SuiteCommand) => {
    if (suite.status !== 'enabled' || pending[suite.name]) return;
    router.push({ pathname: '/', query: { suite: suite.name, suite_command: command.name } });
  };
  const handleUseSuite = (suite: SuiteItem) => {
    if (suite.status !== 'enabled' || pending[suite.name]) return;
    const commands = suite.manifest_snapshot?.commands || [];
    if (commands.length === 1) runCommand(suite, commands[0]);
    else if (detailName === suite.name) setDetailTab('skills');
    else openDetail(suite.name, 'skills');
  };
  const toggle = async (suite: SuiteItem, enabled: boolean) => {
    setPending(previous => ({ ...previous, [suite.name]: true }));
    try {
      const response = await setSuiteEnabled(suite.name, enabled);
      if (!response.data.success) throw new Error(response.data.err_msg || t('plugins_action_error'));
      // Commit presentation state only after the server accepts the change.
      const status = response.data.data?.status || (enabled ? 'enabled' : 'disabled');
      setSuites(previous => previous.map(row => (row.name === suite.name ? { ...row, status } : row)));
      setDetail(previous => (previous?.name === suite.name ? { ...previous, status } : previous));
    } catch (err) {
      message.error(err instanceof Error ? err.message : t('plugins_action_error'));
    } finally {
      setPending(previous => ({ ...previous, [suite.name]: false }));
    }
  };
  const onUpload = async (file: File) => {
    setUploading(true);
    try {
      const form = new FormData();
      form.append('file', file);
      const response = await fetch(`${process.env.API_BASE_URL ?? ''}/api/v1/suites/upload`, {
        method: 'POST',
        body: form,
      });
      const body = await response.json();
      if (!response.ok || !body?.success) throw new Error(body?.detail || body?.err_msg || String(response.status));
      message.success(t('suites_upload_ok'));
      await refresh();
    } catch (err) {
      message.error(`${t('suites_upload_fail')}: ${err instanceof Error ? err.message : ''}`);
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };
  const doUninstall = (suite: SuiteItem) => {
    modal.confirm({
      title: t('plugins_uninstall_title'),
      content: t('plugins_uninstall_hint'),
      okText: t('suites_uninstall'),
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          const response = await uninstallSuite(suite.name);
          if (!response.data.success) throw new Error(response.data.err_msg || t('plugins_action_error'));
          closeDetail();
          message.success(t('plugins_uninstall_ok'));
          await refresh();
        } catch (err) {
          message.error(err instanceof Error ? err.message : t('plugins_action_error'));
          throw err;
        }
      },
    });
  };
  const clearFilters = () => {
    setSearch('');
    setCategory('all');
    setMineOnly(false);
  };
  const hasFilters = !!search.trim() || category !== 'all' || mineOnly;

  const overview = detail && (
    <>
      {!!detail.manifest_snapshot?.artifacts?.length && (
        <section className={styles.detailSection}>
          <h3>{t('plugins_outputs')}</h3>
          <div className={styles.outputs}>
            {detail.manifest_snapshot.artifacts.map((artifact, index) => {
              const display = artifactPresentation(artifact, i18n.language);
              return (
                <span className={styles.output} key={`${display.label}-${index}`}>
                  {display.translationKey ? t(display.translationKey) : display.label}
                </span>
              );
            })}
          </div>
        </section>
      )}
      {!!detail.manifest_snapshot?.recommended_questions?.length && (
        <section className={styles.detailSection}>
          <h3>{t('plugins_examples')}</h3>
          <div className={styles.example}>{detail.manifest_snapshot.recommended_questions[0].text}</div>
        </section>
      )}
      <section className={styles.detailSection}>
        <h3>{t('plugins_review')}</h3>
        <p>{t('plugins_review_hint')}</p>
      </section>
      {detail.readme ? <SuiteReadme label={t('suites_readme_label')}>{detail.readme}</SuiteReadme> : null}
    </>
  );
  const skillPanel = detail && (
    <>
      <section className={styles.detailSection}>
        <h3>{t('suites_cmds')}</h3>
        {(detail.manifest_snapshot?.commands || []).map(command => (
          <button
            type='button'
            className={styles.command}
            key={command.name}
            disabled={detail.status !== 'enabled' || pending[detail.name]}
            onClick={() => runCommand(detail, command)}
          >
            <ThunderboltOutlined aria-hidden />
            <div>
              <strong>{command.display || command.name}</strong>
              <p>{command.description || command.summary}</p>
            </div>
            <ArrowRightOutlined aria-hidden />
          </button>
        ))}
        {!detail.manifest_snapshot?.commands?.length && <p>{t('plugins_no_commands')}</p>}
      </section>
      {!!detail.skill_details?.length && (
        <section className={styles.detailSection}>
          <h3>{t('plugins_skills')}</h3>
          {detail.skill_details.map(skill => (
            <div className={styles.skill} key={skill.name}>
              <strong>{skill.display || skill.name}</strong>
              <p>{skill.description}</p>
            </div>
          ))}
        </section>
      )}
    </>
  );
  const configPanel = detail && (
    <section className={styles.detailSection}>
      <dl className={styles.config}>
        <dt>{t('plugins_publisher')}</dt>
        <dd>{detail.source === 'official' ? 'DB-GPT' : detail.user_name || sourceLabel('enterprise')}</dd>
        <dt>{t('plugins_version')}</dt>
        <dd>v{detail.version}</dd>
        <dt>{t('suites_execution')}</dt>
        <dd>{detail.execution || detail.manifest_snapshot?.execution || '—'}</dd>
        <dt>{t('suites_allowed_tools')}</dt>
        <dd>{detail.manifest_snapshot?.tools?.allow?.join(', ') || '—'}</dd>
        <dt>{t('plugins_denied_tools')}</dt>
        <dd>{detail.manifest_snapshot?.tools?.deny?.join(', ') || '—'}</dd>
        <dt>{t('plugins_context')}</dt>
        <dd>{JSON.stringify(detail.manifest_snapshot?.context_defaults || {}, null, 2)}</dd>
      </dl>
      <p>{t('plugins_declared')}</p>
    </section>
  );

  return (
    <ConstructLayout>
      {contextHolder}
      <div className={styles.page} style={colors}>
        <main className={styles.content}>
          <header className={styles.header}>
            <span className={styles.eyebrow}>{t('suites')}</span>
            <div className={styles.toolbar}>
              <Button type='text' icon={<SettingOutlined />} onClick={() => setManage(previous => !previous)}>
                {manage ? t('plugins_manage_done') : t('plugins_manage')}
              </Button>
              <Dropdown
                trigger={['click']}
                menu={{
                  items: [
                    {
                      key: 'import',
                      label: t('plugins_import'),
                      icon: <UploadOutlined />,
                      onClick: () => fileRef.current?.click(),
                    },
                    {
                      key: 'create',
                      label: t('plugins_create'),
                      icon: <ThunderboltOutlined />,
                      onClick: () => router.push('/?creation_mode=expert_suite'),
                    },
                  ],
                }}
              >
                <Button icon={<PlusOutlined />} loading={uploading}>
                  {t('plugins_add')}
                </Button>
              </Dropdown>
              <input
                ref={fileRef}
                type='file'
                accept='.zip'
                hidden
                onChange={event => event.target.files?.[0] && onUpload(event.target.files[0])}
              />
            </div>
          </header>
          <div className={styles.intro}>
            <div>
              <h1>{t('plugins_title')}</h1>
              <p className={styles.subtitle}>{t('plugins_subtitle')}</p>
            </div>
            <Input
              className={styles.search}
              allowClear
              prefix={<SearchOutlined style={{ color: token.colorTextSecondary }} />}
              placeholder={t('plugins_search')}
              aria-label={t('plugins_search')}
              value={search}
              onChange={event => setSearch(event.target.value)}
            />
          </div>
          <nav className={styles.sources} aria-label={t('plugins_installed')}>
            {sources.map(value => (
              <button
                type='button'
                className={styles.source}
                aria-pressed={source === value}
                key={value}
                onClick={() => {
                  setSource(value);
                  setCategory('all');
                }}
              >
                {sourceLabel(value)}
                <span className={styles.count}>{counts[value]}</span>
              </button>
            ))}
          </nav>
          <div className={styles.filters} aria-label={t('plugins_category_all')}>
            {categories.map(value => (
              <button
                type='button'
                className={styles.filter}
                aria-pressed={category === value}
                key={value}
                onClick={() => setCategory(value)}
              >
                {t(`plugins_category_${value}`)}
              </button>
            ))}
          </div>
          {manage && (
            <div className={styles.manageNote}>
              <span>{t('plugins_manage_hint')}</span>
              <Button
                type={mineOnly ? 'primary' : 'text'}
                size='small'
                onClick={() => setMineOnly(previous => !previous)}
              >
                {t('suites_my_published')}
              </Button>
            </div>
          )}
          {!manage && mineOnly && (
            <Button type='text' size='small' onClick={() => setMineOnly(false)}>
              {t('suites_my_published')} · {t('plugins_clear_filters')}
            </Button>
          )}
          {listError && (
            <Alert
              type='error'
              showIcon
              message={t('plugins_load_error')}
              action={<Button onClick={refresh}>{t('plugins_retry')}</Button>}
              style={{ marginBottom: 20 }}
            />
          )}
          <div className={styles.sectionHeading}>
            <h2>
              {source === 'official'
                ? t('plugins_selected')
                : source === 'enterprise'
                  ? t('plugins_team')
                  : source === 'market'
                    ? t('suites_seg_market')
                    : t('plugins_installed')}
            </h2>
            <span>{t('plugins_count', { count: filtered.length })}</span>
          </div>
          {loading && !suites.length ? (
            <div className={styles.empty}>
              <Spin />
              <p>{t('plugins_loading')}</p>
            </div>
          ) : filtered.length ? (
            <section className={styles.grid} aria-label={t('suites')}>
              {filtered.map(suite => (
                <article className={styles.card} key={suite.name}>
                  <div className={styles.cardHeader}>
                    <SuiteIcon suite={suite} />
                    <div className={styles.identity}>
                      <button className={styles.name} onClick={() => openDetail(suite.name)}>
                        {title(suite)}
                      </button>
                      <div className={styles.publisher}>
                        {suite.source === 'official' && <CheckCircleFilled className={styles.verified} aria-hidden />}
                        {suite.source === 'official' ? 'DB-GPT' : suite.user_name || sourceLabel('enterprise')}
                      </div>
                    </div>
                  </div>
                  <p className={styles.description}>{description(suite)}</p>
                  <div className={styles.cardFooter}>
                    <span>{t('suites_skills_count', { count: suite.manifest_snapshot?.skills?.length || 0 })}</span>
                    <span aria-hidden>·</span>
                    <span className={styles.status}>
                      <span className={`${styles.dot} ${suite.status === 'enabled' ? styles.enabled : ''}`} />
                      {statusLabel(suite)}
                    </span>
                    {manage ? (
                      <Switch
                        size='small'
                        className={styles.cardAction}
                        aria-label={`${t('suites_enable_label')} ${title(suite)}`}
                        checked={suite.status === 'enabled'}
                        loading={pending[suite.name]}
                        onChange={checked => toggle(suite, checked)}
                      />
                    ) : (
                      <Button
                        size='small'
                        className={styles.cardAction}
                        disabled={suite.status !== 'enabled' || pending[suite.name]}
                        onClick={() => handleUseSuite(suite)}
                      >
                        {t('plugins_use')}
                      </Button>
                    )}
                  </div>
                </article>
              ))}
              {source === 'official' && !hasFilters && !manage && (
                <article className={styles.createCard}>
                  <ThunderboltOutlined aria-hidden />
                  <h3>{t('plugins_create_title')}</h3>
                  <p>{t('plugins_create_desc')}</p>
                  <a href='/?creation_mode=expert_suite'>
                    {t('plugins_create')} <ArrowRightOutlined aria-hidden />
                  </a>
                </article>
              )}
            </section>
          ) : !listError ? (
            <div className={styles.empty}>
              <InboxOutlined aria-hidden />
              <h3>
                {hasFilters
                  ? t('plugins_no_results')
                  : source === 'market'
                    ? t('plugins_market_empty')
                    : t('plugins_empty')}
              </h3>
              <p>{hasFilters ? t('plugins_no_results_hint') : t('plugins_empty_hint')}</p>
              <Button onClick={hasFilters ? clearFilters : () => fileRef.current?.click()}>
                {hasFilters ? t('plugins_clear_filters') : t('plugins_import')}
              </Button>
            </div>
          ) : null}
          <div className={styles.note}>
            <BookOutlined aria-hidden />
            <span>{t('plugins_note')}</span>
          </div>
        </main>
      </div>
      <Drawer
        title={t('plugins_details')}
        width='min(620px, 100vw)'
        open={detailName !== null}
        onClose={closeDetail}
        className={styles.drawer}
        rootStyle={colors}
        styles={{ body: { padding: '24px 30px' } }}
        extra={
          detail && (
            <Dropdown
              trigger={['click']}
              menu={{
                items: [
                  { key: 'uninstall', danger: true, label: t('suites_uninstall'), onClick: () => doUninstall(detail) },
                ],
              }}
            >
              <Button aria-label={t('plugins_manage')} icon={<MoreOutlined />} disabled={pending[detail.name]} />
            </Dropdown>
          )
        }
        footer={
          detail && (
            <div className={styles.footer}>
              <label>
                <span>{t('suites_enable_label')}</span>
                <Switch
                  checked={detail.status === 'enabled'}
                  loading={pending[detail.name]}
                  aria-label={`${t('suites_enable_label')} ${title(detail)}`}
                  onChange={checked => toggle(detail, checked)}
                />
              </label>
              <Button
                type='primary'
                disabled={
                  detail.status !== 'enabled' || !detail.manifest_snapshot?.commands?.length || pending[detail.name]
                }
                onClick={() => handleUseSuite(detail)}
              >
                {detail.manifest_snapshot?.commands?.length === 1 ? t('plugins_use') : t('plugins_choose_command')}
                <ArrowRightOutlined />
              </Button>
            </div>
          )
        }
      >
        {detailLoading ? (
          <div className={styles.empty}>
            <Spin />
          </div>
        ) : detailError ? (
          <Alert
            type='error'
            message={t('plugins_detail_error')}
            action={
              <Button onClick={() => detailName && openDetail(detailName, detailTab)}>{t('plugins_retry')}</Button>
            }
          />
        ) : detail ? (
          <>
            <div className={styles.detailHeader}>
              <SuiteIcon suite={detail} size={76} />
              <div>
                <h2>{title(detail)}</h2>
                <div className={styles.publisher}>
                  {detail.source === 'official' && <CheckCircleFilled className={styles.verified} aria-hidden />}
                  {detail.source === 'official' ? 'DB-GPT' : detail.user_name || sourceLabel('enterprise')}
                  <span>·</span>v{detail.version}
                </div>
              </div>
            </div>
            <p className={styles.detailDescription}>{detail.manifest_snapshot?.description}</p>
            <Tabs
              activeKey={detailTab}
              onChange={setDetailTab}
              items={[
                { key: 'overview', label: t('plugins_overview'), children: overview },
                { key: 'skills', label: t('plugins_skills'), children: skillPanel },
                { key: 'configuration', label: t('plugins_configuration'), children: configPanel },
              ]}
            />
          </>
        ) : null}
      </Drawer>
    </ConstructLayout>
  );
}
