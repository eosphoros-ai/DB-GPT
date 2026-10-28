import { FolderOutlined } from '@ant-design/icons';
import { Alert, Button, Drawer, Input, Tag, message } from 'antd';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface SuiteArtifact {
  artifact_id: string;
  draft_id: string;
  revision: number;
  suite_name: string;
  display: string;
  description: string;
  version: string;
  package_digest: string;
  files?: Record<string, string>;
  revisions?: string[];
  configuration?: { database_name?: string };
  validation: {
    status: string;
    errors: string[];
    warnings: string[];
    pending_configuration: string[];
    dependencies: string[];
  };
}

async function request<T = any>(path: string, method = 'GET', body?: any): Promise<T> {
  const response = await fetch(`${process.env.API_BASE_URL || ''}/api/v1/${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json();
  if (!response.ok || payload.success === false) {
    throw new Error(typeof payload.detail === 'string' ? payload.detail : payload.err_msg || 'Request failed');
  }
  return payload.data;
}

export default function SuiteArtifactCard({ content }: { content: SuiteArtifact }) {
  const { i18n } = useTranslation();
  const en = i18n.language.startsWith('en');
  const text = (zh: string, english: string) => (en ? english : zh);
  const router = useRouter();
  const [artifact, setArtifact] = useState(content);
  const [installation, setInstallation] = useState<any>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<Record<string, string>>({});
  const [selected, setSelected] = useState('README.md');
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [database, setDatabase] = useState('');

  const refresh = async (identity = artifact.artifact_id) => {
    const [snapshot, installed] = await Promise.all([
      request<SuiteArtifact>(`suite-artifacts/${identity}`),
      request(`suite-artifacts/${identity}/installation`),
    ]);
    setArtifact(snapshot);
    setInstallation(installed);
    setFiles(snapshot.files || {});
    setDatabase(snapshot.configuration?.database_name || '');
    setDirty(false);
    return snapshot;
  };
  useEffect(() => {
    void refresh(content.artifact_id).catch((err: Error) => setError(err.message));
  }, [content.artifact_id]);

  const perform = async (fn: () => Promise<void>) => {
    setBusy(true);
    setError('');
    try {
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };
  const install = () =>
    perform(async () => {
      const installed = await request(`suite-artifacts/${artifact.artifact_id}/install`, 'POST', {
        package_digest: artifact.package_digest,
      });
      setInstallation(installed);
      window.dispatchEvent(new Event('suites-updated'));
      message.success(
        installed.status === 'enabled'
          ? text('套件已安装，可用于新对话', 'Suite installed and ready')
          : text('套件已安装，请配置数据库', 'Installed; database configuration required'),
      );
    });
  const save = () =>
    perform(async () => {
      // Edit a copy of the frozen package. Never mutate an old artifact or
      // overwrite a concurrent conversation's draft.
      const draft = await request('suite-drafts', 'POST', {
        requirement: artifact.description,
      });
      const written = await request(`suite-drafts/${draft.draft_id}`, 'PATCH', {
        files,
        expected_revision: draft.revision,
      });
      const validation = await request(`suite-drafts/${draft.draft_id}/validate`, 'POST', {
        expected_revision: written.revision,
      });
      if (validation.errors.length) {
        throw new Error(validation.errors.join('\n'));
      }
      const built = await request<SuiteArtifact>(`suite-drafts/${draft.draft_id}/build`, 'POST', {
        expected_revision: written.revision,
        source_artifact_id: content.artifact_id,
      });
      await refresh(built.artifact_id);
      message.success(text('已校验并生成新产物，原产物保留', 'Validated and built a new artifact; original preserved'));
    });
  const useSuite = () =>
    perform(async () => {
      const suite = await request(`suites/${encodeURIComponent(artifact.suite_name)}`);
      const command = suite?.manifest_snapshot?.commands?.[0]?.name;
      if (!command) throw new Error(text('套件没有可用指令', 'No suite command available'));
      void router.push({
        pathname: '/',
        query: {
          suite: artifact.suite_name,
          suite_command: command,
          ...(database ? { database_name: database } : {}),
        },
      });
    });
  const download = () =>
    perform(async () => {
      const response = await fetch(
        `${process.env.API_BASE_URL || ''}/api/v1/suite-artifacts/${artifact.artifact_id}/download`,
      );
      if (!response.ok) throw new Error(text('下载失败', 'Download failed'));
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `${artifact.suite_name}-${artifact.version}.zip`;
      link.click();
      URL.revokeObjectURL(url);
    });
  const configure = () =>
    perform(async () => {
      const installed = await request(`suite-artifacts/${artifact.artifact_id}/configure`, 'POST', {
        database_name: database,
      });
      setInstallation(installed);
      window.dispatchEvent(new Event('suites-updated'));
    });

  const status = installation
    ? installation.status === 'enabled'
      ? text('已安装', 'Installed')
      : text('待配置 / 已停用', 'Configuration required / disabled')
    : text('校验通过 · 未安装', 'Validated · Not installed');
  return (
    <>
      <div
        data-testid='expert-suite-artifact'
        className='w-full max-w-[420px] rounded-xl border border-green-200 dark:border-green-900 bg-white dark:bg-[#111217] p-4'
      >
        <div className='flex gap-3 items-start'>
          <FolderOutlined className='text-green-600 text-2xl mt-1' />
          <div className='min-w-0 flex-1'>
            <div className='font-semibold break-words'>{artifact.display}</div>
            <div className='text-xs text-gray-500 mt-1'>
              {text('专家套件', 'Expert suite')} · v{artifact.version} · {text('当前实例', 'This instance')}
            </div>
            <p className='text-xs text-gray-500 my-2 line-clamp-2'>{artifact.description}</p>
            <Tag color={installation ? 'green' : 'blue'}>{status}</Tag>
          </div>
        </div>
        {error && !open && <Alert type='error' className='mt-2' message={error} />}
        <div className='flex flex-wrap gap-2 mt-3'>
          <Button
            size='small'
            onClick={() => {
              setOpen(true);
              void perform(async () => {
                await refresh();
              });
            }}
          >
            {text('预览与编辑', 'Preview & edit')}
          </Button>
          <Button size='small' onClick={download} disabled={busy}>
            {text('下载套件', 'Download')}
          </Button>
          {!installation && (
            <Button size='small' type='primary' loading={busy} onClick={install}>
              {text('一键安装', 'Install')}
            </Button>
          )}
          {installation?.status === 'enabled' && (
            <Button size='small' type='primary' onClick={useSuite}>
              {text('用于新对话', 'Use in new chat')}
            </Button>
          )}
          {installation?.status !== 'enabled' && installation && (
            <Button size='small' onClick={() => setOpen(true)}>
              {text('配置并启用', 'Configure')}
            </Button>
          )}
        </div>
      </div>
      <Drawer
        title={`${artifact.display} · ${text('专家套件', 'Expert suite')}`}
        open={open}
        onClose={() => setOpen(false)}
        width='min(920px, 100vw)'
      >
        <div className='flex flex-wrap gap-2 mb-3'>
          <Tag>{text('当前实例安装', 'Instance installation')}</Tag>
          <Tag color='green'>{status}</Tag>
          <Tag>{text('尚未真实试跑', 'Not trial run')}</Tag>
        </div>
        <div className='text-xs text-gray-500 mb-3 break-all'>
          {artifact.suite_name} · v{artifact.version} · SHA256 {artifact.package_digest}
        </div>
        {!!artifact.revisions?.length && (
          <Button
            className='mb-3'
            onClick={() =>
              perform(async () => {
                await refresh(artifact.revisions!.at(-1)!);
              })
            }
          >
            {text('查看后续编辑产物', 'View later revision')}
          </Button>
        )}
        {error && <Alert type='error' showIcon message={error} className='mb-3 whitespace-pre-wrap' />}
        {!!artifact.validation.pending_configuration.length && installation?.status !== 'enabled' && (
          <Alert
            className='mb-3'
            type='info'
            message={text(
              '需要配置数据库；完成配置前保持停用。',
              'A database is required; the suite stays disabled until configured.',
            )}
          />
        )}
        {installation && artifact.validation.pending_configuration.includes('database') && (
          <div className='flex gap-2 mb-3'>
            <Input
              aria-label={text('数据库名称', 'Database name')}
              placeholder={text('已接入的数据库名称', 'Connected database name')}
              value={database}
              onChange={event => setDatabase(event.target.value)}
            />
            <Button onClick={configure} loading={busy} disabled={!database}>
              {text('验证配置并启用', 'Verify & enable')}
            </Button>
          </div>
        )}
        <div className='mb-3 text-sm'>
          {text('工具依赖：', 'Tool dependencies: ')}
          {artifact.validation.dependencies.join(', ') || text('无', 'None')}
        </div>
        <select
          className='w-full mb-3 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent px-3 py-2'
          aria-label={text('套件文件', 'Suite file')}
          value={selected}
          disabled={busy}
          onChange={event => setSelected(event.target.value)}
        >
          {Object.keys(files)
            .sort()
            .map(value => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
        </select>
        <Input.TextArea
          aria-label={text('文件正文', 'File content')}
          className='font-mono'
          value={files[selected] || ''}
          readOnly={busy}
          onChange={event => {
            setFiles(previous => ({ ...previous, [selected]: event.target.value }));
            setDirty(true);
          }}
          autoSize={{ minRows: 16, maxRows: 25 }}
        />
        <div className='flex flex-wrap gap-2 mt-4'>
          <Button type='primary' onClick={save} disabled={!dirty} loading={busy}>
            {text('保存、校验并生成新产物', 'Save, validate & build')}
          </Button>
          <Button disabled={busy || dirty} onClick={download}>
            {text('下载完整套件', 'Download package')}
          </Button>
          {!installation && (
            <Button disabled={dirty} onClick={install} loading={busy}>
              {text('一键安装', 'Install')}
            </Button>
          )}
          {installation?.status === 'enabled' && (
            <Button onClick={useSuite}>{text('用于新对话', 'Use in new chat')}</Button>
          )}
        </div>
        <p className='text-xs text-gray-500 mt-3'>
          {text(
            '编辑不改变原产物；结构校验通过后生成新产物。安装不会覆盖同名套件，冲突时请修改 plugin.json 中的 name。',
            'Edits build a new artifact after validation. Existing suites are preserved; change plugin.json name to resolve a conflict.',
          )}
        </p>
      </Drawer>
    </>
  );
}
