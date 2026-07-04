import {
  apiInterceptors,
  getChunkList,
  getCodeGraphVisualizeHtml,
  getKnowledgeSpaceStats,
  getSpaceList,
} from '@/client/api';
import DocPanel from '@/components/knowledge/doc-panel';
import KnowledgeTree from '@/components/knowledge/knowledge-tree';
import { IDocument, ISpace, KnowledgeSpaceStats } from '@/types/knowledge';
import {
  ApartmentOutlined,
  ArrowLeftOutlined,
  CodeOutlined,
  FileTextOutlined,
  GitlabOutlined,
  NodeIndexOutlined,
  PartitionOutlined,
  ShareAltOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { Button, Card, Col, Empty, Progress, Row, Segmented, Space, Spin, Statistic, Tag } from 'antd';
import { useRouter } from 'next/router';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

type ViewMode = 'files' | 'graph';

/**
 * Knowledge Space Detail Page.
 *
 * Layout: Tree sidebar (left) + Content area (right).
 * View modes: File View (document list + chunk detail) / Code Graph View
 */
export default function KnowledgeDetailPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const spaceName = (router.query.spaceName as string) || '';

  const [currentSpace, setCurrentSpace] = useState<ISpace | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>('files');

  // Stats state
  const [stats, setStats] = useState<KnowledgeSpaceStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  // Code graph state
  const graphIframeRef = useRef<HTMLIFrameElement | null>(null);
  const [graphHtml, setGraphHtml] = useState<string | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);

  // Document detail state (when a doc is selected in the tree)
  const [selectedDoc, setSelectedDoc] = useState<IDocument | null>(null);
  const [chunks, setChunks] = useState<any[]>([]);
  const [chunksLoading, setChunksLoading] = useState(false);

  useEffect(() => {
    if (!spaceName) return;
    (async () => {
      setLoading(true);
      const [, data] = await apiInterceptors(getSpaceList({ name: spaceName }));
      if (data && data.length > 0) {
        setCurrentSpace(data[0]);
      }
      setLoading(false);
    })();
  }, [spaceName]);

  // Fetch stats
  useEffect(() => {
    if (!spaceName) return;
    (async () => {
      setStatsLoading(true);
      const [, data] = await apiInterceptors(getKnowledgeSpaceStats(spaceName));
      if (data) {
        setStats(data);
      }
      setStatsLoading(false);
    })();
  }, [spaceName]);

  // Fetch code graph HTML when switching to graph view
  useEffect(() => {
    if (viewMode !== 'graph' || !spaceName) {
      setGraphHtml(null);
      setGraphError(null);
      return;
    }
    (async () => {
      setGraphLoading(true);
      setGraphError(null);
      setGraphHtml(null);
      try {
        const html = await getCodeGraphVisualizeHtml(spaceName);
        if (!html || html.includes('No code graph found')) {
          setGraphError('No code graph found. Please build the code graph first.');
        } else {
          setGraphHtml(html);
        }
      } catch (err: any) {
        setGraphError(err?.message || t('No_Results') || 'Failed to load code graph');
      }
      setGraphLoading(false);
    })();
  }, [viewMode, spaceName, t]);

  // Fetch chunks when a document is selected
  useEffect(() => {
    if (!selectedDoc || !spaceName) {
      setChunks([]);
      return;
    }
    (async () => {
      setChunksLoading(true);
      const [, data] = await apiInterceptors(
        getChunkList(spaceName, {
          document_id: String(selectedDoc.id),
          page: 1,
          page_size: 50,
        }),
      );
      setChunks(data?.data || []);
      setChunksLoading(false);
    })();
  }, [selectedDoc, spaceName]);

  const handleSelectSpace = (space: ISpace) => {
    setCurrentSpace(space);
    setSelectedDoc(null);
    setChunks([]);
    router.replace(`/construct/knowledge/detail?spaceName=${space.name}`, undefined, { shallow: true });
  };

  const handleSelectDocument = (doc: IDocument | null) => {
    setSelectedDoc(doc);
  };

  const handleBack = () => {
    router.push('/construct/knowledge');
  };

  const handleBackToDocList = () => {
    setSelectedDoc(null);
    setChunks([]);
  };

  const viewModeOptions = [
    {
      label: (
        <span className='flex items-center gap-1.5'>
          <FileTextOutlined />
          {t('File_View')}
        </span>
      ),
      value: 'files',
    },
    {
      label: (
        <span className='flex items-center gap-1.5'>
          <ApartmentOutlined />
          {t('Code_Graph_View')}
        </span>
      ),
      value: 'graph',
    },
  ];

  /** Render the metadata stats panel */
  const renderStatsPanel = () => {
    if (statsLoading) {
      return (
        <div className='px-4 py-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-[#1e2130]'>
          <Spin size='small' />
        </div>
      );
    }
    if (!stats) return null;

    const hasSyncProgress = stats.sync_status && stats.sync_total_files !== null && stats.sync_total_files > 0;
    const hasGraphStats =
      stats.graph_vertex_count !== null || stats.graph_edge_count !== null || stats.graph_community_count !== null;

    const syncPercent =
      hasSyncProgress && stats.sync_total_files
        ? Math.round(((stats.sync_finished || 0) / stats.sync_total_files) * 100)
        : 0;

    return (
      <div className='px-4 py-3 border-b dark:border-gray-700 bg-gray-50 dark:bg-[#1e2130]'>
        {/* Tags row */}
        <div className='flex items-center gap-2 mb-3 flex-wrap'>
          {stats.domain_type && <Tag color='blue'>{stats.domain_type}</Tag>}
          {stats.vector_type && <Tag color='purple'>{stats.vector_type}</Tag>}
          {stats.index_methods &&
            stats.index_methods.map((m: string) => (
              <Tag key={m} color='geekblue'>
                {m}
              </Tag>
            ))}
          {stats.repo_url && (
            <Tag icon={<GitlabOutlined />} color='volcano'>
              {stats.branch || 'main'}
            </Tag>
          )}
        </div>

        {/* Stats row */}
        <Row gutter={16}>
          <Col span={4}>
            <Statistic
              title={t('Documents')}
              value={stats.document_count}
              prefix={<FileTextOutlined />}
              valueStyle={{ fontSize: 18 }}
            />
          </Col>
          <Col span={4}>
            <Statistic
              title={t('Chunks')}
              value={stats.chunk_count}
              prefix={<PartitionOutlined />}
              valueStyle={{ fontSize: 18 }}
            />
          </Col>
          {hasGraphStats && (
            <>
              <Col span={4}>
                <Statistic
                  title={t('Graph_Nodes')}
                  value={stats.graph_vertex_count ?? 0}
                  prefix={<NodeIndexOutlined />}
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col span={4}>
                <Statistic
                  title={t('Graph_Edges')}
                  value={stats.graph_edge_count ?? 0}
                  prefix={<ShareAltOutlined />}
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
              <Col span={4}>
                <Statistic
                  title={t('Communities')}
                  value={stats.graph_community_count ?? 0}
                  prefix={<TeamOutlined />}
                  valueStyle={{ fontSize: 18 }}
                />
              </Col>
            </>
          )}
        </Row>

        {/* Sync progress bar (for GitRepo spaces) */}
        {hasSyncProgress && (
          <div className='mt-3'>
            <div className='flex items-center justify-between mb-1'>
              <span className='text-xs text-gray-500 dark:text-gray-400'>{t('Sync_Progress')}</span>
              <span className='text-xs text-gray-500 dark:text-gray-400'>
                {stats.sync_finished || 0}/{stats.sync_total_files} {t('Files')}
                {stats.sync_failed ? ` (${stats.sync_failed} failed)` : ''}
              </span>
            </div>
            <Progress
              percent={syncPercent}
              size='small'
              status={
                stats.sync_status === 'FAILED' ? 'exception' : stats.sync_status === 'RUNNING' ? 'active' : 'success'
              }
            />
          </div>
        )}
      </div>
    );
  };

  return (
    <div className='h-full flex flex-col'>
      {/* Header */}
      <div className='flex items-center justify-between px-4 py-3 border-b dark:border-gray-700 bg-white dark:bg-[#232734]'>
        <div className='flex items-center gap-3'>
          <Button
            type='text'
            icon={<ArrowLeftOutlined />}
            onClick={selectedDoc ? handleBackToDocList : handleBack}
            className='text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'
          />
          <div>
            <h2 className='text-base font-semibold text-gray-800 dark:text-gray-200 m-0'>
              {selectedDoc ? selectedDoc.doc_name : currentSpace?.name || spaceName}
            </h2>
            <p className='text-xs text-gray-400 dark:text-gray-500 m-0 mt-0.5 truncate max-w-[400px]'>
              {selectedDoc
                ? `${selectedDoc.chunk_size} chunks · ${selectedDoc.doc_type || 'Document'}`
                : currentSpace?.desc || ''}
            </p>
          </div>
        </div>
        <Space>
          <Segmented options={viewModeOptions} value={viewMode} onChange={val => setViewMode(val as ViewMode)} />
        </Space>
      </div>

      {/* Stats Panel */}
      {renderStatsPanel()}

      {/* Body: Tree + Content */}
      <div className='flex-1 flex overflow-hidden'>
        {/* Tree Sidebar */}
        <div className='w-[280px] min-w-[280px] border-r dark:border-gray-700 bg-white dark:bg-[#1e2130] overflow-hidden'>
          <KnowledgeTree
            currentSpaceName={spaceName}
            currentSpace={currentSpace}
            onSelectDocument={handleSelectDocument}
            onSelectSpace={handleSelectSpace}
          />
        </div>

        {/* Content Area */}
        <div className='flex-1 overflow-auto bg-gray-50 dark:bg-[#232734]'>
          {loading ? (
            <div className='flex items-center justify-center h-full'>
              <Spin size='large' />
            </div>
          ) : viewMode === 'graph' ? (
            /* Code Graph View */
            <div className='h-full w-full flex flex-col bg-white dark:bg-[#232734]'>
              {graphLoading ? (
                <div className='flex items-center justify-center h-full'>
                  <Spin size='large' />
                </div>
              ) : graphError ? (
                <div className='flex flex-col items-center justify-center h-full text-gray-400 gap-3'>
                  <CodeOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                  <p className='text-sm'>{graphError}</p>
                </div>
              ) : graphHtml ? (
                <iframe
                  ref={graphIframeRef}
                  title='code-graph'
                  srcDoc={graphHtml}
                  className='flex-1 w-full border-0'
                  sandbox='allow-scripts allow-same-origin'
                />
              ) : (
                <div className='flex flex-col items-center justify-center h-full text-gray-400 gap-3'>
                  <CodeOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                  <p className='text-sm'>{t('Code_Graph_View_desc')}</p>
                </div>
              )}
            </div>
          ) : selectedDoc ? (
            /* Document Content View — show chunks */
            <div className='p-4'>
              <div className='mb-4 flex items-center justify-between'>
                <div className='flex items-center gap-2'>
                  <FileTextOutlined style={{ color: '#1677FF', fontSize: 16 }} />
                  <span className='text-sm font-semibold text-gray-800 dark:text-gray-200'>{selectedDoc.doc_name}</span>
                  <Tag>{selectedDoc.doc_type}</Tag>
                  <Tag color='blue'>{selectedDoc.chunk_size} chunks</Tag>
                </div>
              </div>
              <Spin spinning={chunksLoading}>
                {chunks.length > 0 ? (
                  <div className='grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4'>
                    {chunks.map((chunk: any, index: number) => (
                      <Card
                        key={chunk.id || index}
                        size='small'
                        className='rounded-lg dark:bg-[#2a2d3a] hover:shadow-md transition-shadow'
                        title={
                          <Space>
                            <Tag color='blue'># {index + 1}</Tag>
                          </Space>
                        }
                      >
                        <div className='text-sm text-gray-700 dark:text-gray-300 whitespace-pre-wrap line-clamp-8'>
                          {chunk.content}
                        </div>
                        {chunk.meta_info && (
                          <div className='mt-2 pt-2 border-t dark:border-gray-600'>
                            <span className='text-xs text-gray-400'>
                              {typeof chunk.meta_info === 'string'
                                ? chunk.meta_info.slice(0, 200)
                                : JSON.stringify(chunk.meta_info).slice(0, 200)}
                            </span>
                          </div>
                        )}
                      </Card>
                    ))}
                  </div>
                ) : (
                  <Empty description={t('No_Results')} />
                )}
              </Spin>
            </div>
          ) : currentSpace ? (
            /* Space overview — document list */
            <DocPanel
              space={currentSpace}
              onAddDoc={(_name: string) => {
                // Could navigate to add doc flow
              }}
              onDeleteDoc={() => {
                // Refresh handled internally
              }}
            />
          ) : (
            <div className='flex items-center justify-center h-full text-gray-400'>Knowledge space not found</div>
          )}
        </div>
      </div>
    </div>
  );
}
