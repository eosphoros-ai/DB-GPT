import {
  apiInterceptors,
  getChunkList,
  getCodeGraphVisualizeHtml,
  getKnowledgeSpaceStats,
  getSpaceList,
  kbCat,
} from '@/client/api';
import CatResultViewer from '@/components/knowledge/cat-result-viewer';
import EmbeddedChat from '@/components/knowledge/embedded-chat';
import DocPanel from '@/components/knowledge/doc-panel';
import KnowledgeTree from '@/components/knowledge/knowledge-tree';
import { IDocument, ISpace, KbFileEntry, KnowledgeSpaceStats } from '@/types/knowledge';
import {
  ApartmentOutlined,
  ArrowLeftOutlined,
  CodeOutlined,
  FileTextOutlined,
  GitlabOutlined,
  MessageOutlined,
  NodeIndexOutlined,
  PartitionOutlined,
  ShareAltOutlined,
  TeamOutlined,
} from '@ant-design/icons';
import { Button, Card, Col, Empty, Progress, Row, Space, Spin, Statistic, Tabs, Tag } from 'antd';
import { useRouter } from 'next/router';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

type ViewTab = 'files' | 'chat' | 'graph';

/**
 * Knowledge Space Detail Page.
 *
 * Layout: Tree sidebar (left) + Content area (right).
 * View tabs: Files / Chat / Code Graph
 */
export default function KnowledgeDetailPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const spaceName = (router.query.spaceName as string) || '';

  const [currentSpace, setCurrentSpace] = useState<ISpace | null>(null);
  const [loading, setLoading] = useState(true);
  const [viewTab, setViewTab] = useState<ViewTab>('files');

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

  // Source file state (when a file is selected in the tree)
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>('');
  const [fileContentLoading, setFileContentLoading] = useState(false);

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

  // Fetch code graph HTML when switching to graph tab
  useEffect(() => {
    if (viewTab !== 'graph' || !spaceName) {
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
  }, [viewTab, spaceName, t]);

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

  // Fetch file content via kbCat when a file is selected
  useEffect(() => {
    if (!selectedFilePath || !currentSpace?.id) {
      setFileContent('');
      return;
    }
    (async () => {
      setFileContentLoading(true);
      const [, data] = await apiInterceptors(
        kbCat(currentSpace.id, { path: selectedFilePath, start_line: 1, end_line: 0 }),
      );
      setFileContent(data || '');
      setFileContentLoading(false);
    })();
  }, [selectedFilePath, currentSpace?.id]);

  const handleSelectSpace = (space: ISpace) => {
    setCurrentSpace(space);
    setSelectedDoc(null);
    setChunks([]);
    setSelectedFilePath(null);
    setFileContent('');
    router.replace(`/construct/knowledge/detail?spaceName=${space.name}`, undefined, { shallow: true });
  };

  const handleSelectDocument = (doc: IDocument | null) => {
    setSelectedDoc(doc);
  };

  const handleSelectFile = (file: KbFileEntry | null) => {
    setSelectedFilePath(file?.path || null);
    setFileContent('');
  };

  const handleBack = () => {
    router.push('/construct/knowledge');
  };

  const handleBackToDocList = () => {
    setSelectedDoc(null);
    setChunks([]);
    setSelectedFilePath(null);
    setFileContent('');
  };

  const handleTabChange = (key: string) => {
    setViewTab(key as ViewTab);
    // When switching away from files view, deselect doc
    if (key !== 'files') {
      setSelectedDoc(null);
      setChunks([]);
      setSelectedFilePath(null);
      setFileContent('');
    }
  };

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

  /** Render the Files tab content */
  const renderFilesContent = () => {
    if (selectedDoc) {
      return (
        <div className='h-full flex flex-col'>
          {/* Document header */}
          <div className='px-4 py-3 flex items-center gap-2 border-b dark:border-gray-700 bg-white dark:bg-[#232734]'>
            <FileTextOutlined style={{ color: '#1677FF', fontSize: 16 }} />
            <span className='text-sm font-semibold text-gray-800 dark:text-gray-200'>{selectedDoc.doc_name}</span>
            <Tag>{selectedDoc.doc_type}</Tag>
            <Tag color='blue'>{selectedDoc.chunk_size} chunks</Tag>
          </div>

          {/* Side-by-side: Source | Chunks */}
          {selectedFilePath ? (
            <div className='flex-1 flex overflow-hidden'>
              {/* Left: Source file */}
              <div className='w-1/2 min-w-0 border-r dark:border-gray-700 flex flex-col overflow-hidden'>
                <div className='px-3 py-2 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider border-b dark:border-gray-700 bg-gray-50 dark:bg-[#1e2130]'>
                  {t('Source_View')}
                </div>
                <div className='flex-1 overflow-auto p-3'>
                  <Spin spinning={fileContentLoading}>
                    {fileContent ? (
                      <CatResultViewer content={fileContent} />
                    ) : (
                      <Empty description={t('No_Results')} />
                    )}
                  </Spin>
                </div>
              </div>
              {/* Right: Chunks */}
              <div className='w-1/2 min-w-0 flex flex-col overflow-hidden'>
                <div className='px-3 py-2 text-xs font-semibold text-gray-400 dark:text-gray-500 uppercase tracking-wider border-b dark:border-gray-700 bg-gray-50 dark:bg-[#1e2130]'>
                  {t('Chunks_View')}
                </div>
                <div className='flex-1 overflow-auto p-3'>
                  <Spin spinning={chunksLoading}>
                    {chunks.length > 0 ? (
                      <div className='flex flex-col gap-3'>
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
              </div>
            </div>
          ) : (
            /* Fallback: no file path available (document list mode) — show chunks only */
            <div className='flex-1 overflow-auto p-4'>
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
          )}
        </div>
      );
    }

    // No doc selected — show DocPanel
    if (currentSpace) {
      return (
        <DocPanel
          space={currentSpace}
          hideRecallTest
          hideSearchTools
          onAddDoc={(_name: string) => {
            // Could navigate to add doc flow
          }}
          onDeleteDoc={() => {
            // Refresh handled internally
          }}
        />
      );
    }

    return <div className='flex items-center justify-center h-full text-gray-400'>Knowledge space not found</div>;
  };

  /** Render the Chat tab content */
  const renderChatContent = () => {
    return <EmbeddedChat spaceName={spaceName} />;
  };

  /** Render the Code Graph tab content */
  const renderGraphContent = () => {
    if (graphLoading) {
      return (
        <div className='flex items-center justify-center h-full'>
          <Spin size='large' />
        </div>
      );
    }
    if (graphError) {
      return (
        <div className='flex flex-col items-center justify-center h-full text-gray-400 gap-3'>
          <CodeOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
          <p className='text-sm'>{graphError}</p>
        </div>
      );
    }
    if (graphHtml) {
      return (
        <iframe
          ref={graphIframeRef}
          title='code-graph'
          srcDoc={graphHtml}
          className='w-full h-full border-0'
          sandbox='allow-scripts allow-same-origin'
        />
      );
    }
    return (
      <div className='flex flex-col items-center justify-center h-full text-gray-400 gap-3'>
        <CodeOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
        <p className='text-sm'>{t('Code_Graph_View_desc')}</p>
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
            onClick={selectedDoc && viewTab === 'files' ? handleBackToDocList : handleBack}
            className='text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'
          />
          <Tabs
            activeKey={viewTab}
            onChange={handleTabChange}
            size='small'
            items={[
              {
                key: 'files',
                label: (
                  <span className='flex items-center gap-1.5'>
                    <FileTextOutlined />
                    {t('File_View')}
                  </span>
                ),
              },
              {
                key: 'chat',
                label: (
                  <span className='flex items-center gap-1.5'>
                    <MessageOutlined />
                    {t('Chat')}
                  </span>
                ),
              },
              {
                key: 'graph',
                label: (
                  <span className='flex items-center gap-1.5'>
                    <ApartmentOutlined />
                    {t('Code_Graph_View')}
                  </span>
                ),
              },
            ]}
          />
        </div>
        <div>
          <h2 className='text-base font-semibold text-gray-800 dark:text-gray-200 m-0'>
            {selectedDoc && viewTab === 'files' ? selectedDoc.doc_name : currentSpace?.name || spaceName}
          </h2>
          <p className='text-xs text-gray-400 dark:text-gray-500 m-0 mt-0.5 truncate max-w-[400px]'>
            {selectedDoc && viewTab === 'files'
              ? `${selectedDoc.chunk_size} chunks · ${selectedDoc.doc_type || 'Document'}`
              : currentSpace?.desc || ''}
          </p>
        </div>
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
            onSelectDocument={doc => {
              handleSelectDocument(doc);
              if (viewTab !== 'files') {
                setViewTab('files');
              }
            }}
            onSelectSpace={handleSelectSpace}
            onSelectFile={handleSelectFile}
          />
        </div>

        {/* Content Area */}
        <div className='flex-1 overflow-hidden bg-gray-50 dark:bg-[#232734]'>
          {loading ? (
            <div className='flex items-center justify-center h-full'>
              <Spin size='large' />
            </div>
          ) : viewTab === 'files' ? (
            renderFilesContent()
          ) : viewTab === 'chat' ? (
            renderChatContent()
          ) : (
            renderGraphContent()
          )}
        </div>
      </div>
    </div>
  );
}