import { exportDashboardProject, getDashboardArtifacts } from '@/client/api';
import { DashboardArtifactBundle } from '@/types/dashboard';
import { DownloadOutlined, FileOutlined, FolderOpenOutlined } from '@ant-design/icons';
import { Alert, Button, Drawer, Empty, Spin } from 'antd';
import { useEffect, useMemo, useState } from 'react';

interface DashboardArtifactPanelProps {
  dashboardId: string;
  open: boolean;
  onClose: () => void;
}

export default function DashboardArtifactPanel({ dashboardId, open, onClose }: DashboardArtifactPanelProps) {
  const [result, setResult] = useState<{
    dashboardId: string;
    bundle: DashboardArtifactBundle | null;
    error: string;
  } | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    if (!open) return;
    let active = true;
    getDashboardArtifacts(dashboardId)
      .then(response => {
        if (!active) return;
        const next = response.data.data;
        setResult({ dashboardId, bundle: next, error: '' });
        setSelectedPath(current =>
          current && next.files.some(file => file.path === current) ? current : next.files[0]?.path || null,
        );
      })
      .catch(reason => {
        if (!active) return;
        setResult({
          dashboardId,
          bundle: null,
          error: reason instanceof Error ? reason.message : '加载工程文件失败',
        });
      });
    return () => {
      active = false;
    };
  }, [dashboardId, open]);

  const loaded = result?.dashboardId === dashboardId ? result : null;
  const bundle = loaded?.bundle || null;
  const error = loaded?.error || '';
  const loading = open && !loaded;

  const selectedFile = useMemo(
    () => bundle?.files.find(file => file.path === selectedPath) || null,
    [bundle, selectedPath],
  );

  const download = async () => {
    setDownloading(true);
    try {
      const response = await exportDashboardProject(dashboardId);
      const url = URL.createObjectURL(response.data as unknown as Blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${bundle?.root || `dashboard-${dashboardId}`}.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (reason) {
      setResult(current => ({
        dashboardId,
        bundle: current?.dashboardId === dashboardId ? current.bundle : null,
        error: reason instanceof Error ? reason.message : '导出工程失败',
      }));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <Drawer
      title='看板工程文件'
      width='min(920px, 92vw)'
      open={open}
      onClose={onClose}
      extra={
        <Button icon={<DownloadOutlined />} loading={downloading} onClick={download}>
          ZIP 下载
        </Button>
      }
    >
      {loading ? (
        <div className='flex h-60 items-center justify-center'>
          <Spin />
        </div>
      ) : error ? (
        <Alert type='error' showIcon message={error} />
      ) : bundle ? (
        <div className='flex min-h-[560px] overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700'>
          <aside className='w-64 shrink-0 overflow-y-auto border-r border-gray-200 bg-gray-50 p-3 dark:border-gray-700 dark:bg-black/20'>
            <div className='mb-3 flex items-center gap-2 text-xs font-medium text-gray-500'>
              <FolderOpenOutlined />
              <span className='truncate'>{bundle.root}</span>
            </div>
            <div className='space-y-1'>
              {bundle.files.map(file => (
                <button
                  key={file.path}
                  type='button'
                  className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs ${
                    selectedPath === file.path
                      ? 'bg-blue-100 text-blue-800 dark:bg-blue-950/50 dark:text-blue-100'
                      : 'text-gray-600 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-white/5'
                  }`}
                  onClick={() => setSelectedPath(file.path)}
                >
                  <FileOutlined />
                  <span className='truncate'>{file.path}</span>
                </button>
              ))}
            </div>
          </aside>
          <main className='min-w-0 flex-1 overflow-auto bg-[#0d1117] text-gray-100'>
            {selectedFile ? (
              <>
                <div className='sticky top-0 border-b border-white/10 bg-[#161b22] px-4 py-2 text-xs text-gray-400'>
                  {selectedFile.path} · {selectedFile.language}
                </div>
                <pre className='m-0 whitespace-pre-wrap break-words p-4 font-mono text-xs leading-5'>
                  {selectedFile.content}
                </pre>
              </>
            ) : (
              <Empty description='没有可查看的文件' />
            )}
          </main>
        </div>
      ) : (
        <Empty description='没有工程文件' />
      )}
    </Drawer>
  );
}
