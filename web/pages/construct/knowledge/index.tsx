import { apiInterceptors, delSpace, getKnowledgeSpaceStats, getSpaceConfig, getSpaceList } from '@/client/api';
import DocTypeForm from '@/components/knowledge/doc-type-form';
import DocUploadForm from '@/components/knowledge/doc-upload-form';
import GitRepoSyncForm from '@/components/knowledge/git-repo-sync-form';
import Segmentation from '@/components/knowledge/segmentation';
import SpaceForm from '@/components/knowledge/space-form';
import BlurredCard, { InnerDropdown } from '@/new-components/common/blurredCard';
import ConstructLayout from '@/new-components/layout/Construct';
import { File, ISpace, IStorage, StepChangeParams } from '@/types/knowledge';
import {
  NodeIndexOutlined,
  PlusOutlined,
  ReadOutlined,
  SearchOutlined,
  ShareAltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import { Button, Input, Modal, Spin, Tag } from 'antd';
import classNames from 'classnames';
import { debounce } from 'lodash';
import moment from 'moment';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

const Knowledge = () => {
  const [spaceList, setSpaceList] = useState<Array<ISpace> | null>([]);
  const [isAddShow, setIsAddShow] = useState<boolean>(false);

  const [activeStep, setActiveStep] = useState<number>(0);
  const [spaceName, setSpaceName] = useState<string>('');
  const [files, setFiles] = useState<Array<File>>([]);
  const [docType, setDocType] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [spaceConfig, setSpaceConfig] = useState<IStorage | null>(null);
  const [spaceStats, setSpaceStats] = useState<
    Record<string, { vertexCount: number | null; edgeCount: number | null }>
  >({});

  const { t } = useTranslation();
  const router = useRouter();

  async function getSpaces(params?: any) {
    setLoading(true);
    const [_, data] = await apiInterceptors(getSpaceList({ ...params }));
    setLoading(false);
    setSpaceList(data);
    // Fetch stats for each space (graph info)
    if (data) {
      for (const space of data) {
        try {
          const [, stats] = await apiInterceptors(getKnowledgeSpaceStats(space.id));
          if (stats) {
            setSpaceStats(prev => ({
              ...prev,
              [space.name]: {
                vertexCount: stats.graph_vertex_count ?? null,
                edgeCount: stats.graph_edge_count ?? null,
              },
            }));
          }
        } catch {
          /* ignore individual stat failures */
        }
      }
    }
  }

  async function getSpaceConfigs() {
    const [_, data] = await apiInterceptors(getSpaceConfig());
    if (!data) return null;
    setSpaceConfig(data.storage);
  }

  useEffect(() => {
    getSpaces();
    getSpaceConfigs();
  }, []);

  const handleStepChange = ({ label, spaceName, docType, files }: StepChangeParams) => {
    if (label === 'finish') {
      setIsAddShow(false);
      getSpaces();
      setSpaceName('');
      setDocType('');
      localStorage.removeItem('cur_space_id');
    } else if (label === 'forward') {
      activeStep === 0 && getSpaces();
      setActiveStep(step => step + 1);
    } else {
      setActiveStep(step => step - 1);
    }
    files && setFiles(files);
    spaceName && setSpaceName(spaceName);
    docType && setDocType(docType);
  };

  const showDeleteConfirm = (space: ISpace) => {
    Modal.confirm({
      title: t('Tips'),
      icon: <WarningOutlined />,
      content: `${t('Del_Knowledge_Tips')}?`,
      okText: 'Yes',
      okType: 'danger',
      cancelText: 'No',
      async onOk() {
        await apiInterceptors(delSpace({ name: space?.name }));
        getSpaces();
      },
    });
  };

  const onSearch = async (e: any) => {
    getSpaces({ name: e.target.value });
  };

  return (
    <ConstructLayout>
      <Spin spinning={loading}>
        <div className='page-body p-4 md:p-6 h-[90vh] overflow-auto'>
          {/* <Button
            type="primary"
            className="flex items-center"
            icon={<PlusOutlined />}
            onClick={() => {
              setIsAddShow(true);
            }}
          >
            Create
          </Button> */}
          <div className='flex justify-between items-center mb-6'>
            <div className='flex items-center gap-4'>
              <Input
                variant='filled'
                prefix={<SearchOutlined />}
                placeholder={t('please_enter_the_keywords')}
                onChange={debounce(onSearch, 300)}
                allowClear
                className='w-[230px] h-[40px] border-1 border-white backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
              />
            </div>

            <div className='flex items-center gap-4'>
              <Button
                className='border-none text-white bg-button-gradient'
                icon={<PlusOutlined />}
                onClick={() => {
                  setIsAddShow(true);
                }}
              >
                {t('create_knowledge')}
              </Button>
            </div>
          </div>
          <div className='flex flex-wrap mt-4 mx-[-8px]'>
            {spaceList?.map((space: ISpace) => (
              <BlurredCard
                onClick={() => {
                  router.push(`/construct/knowledge/detail?spaceName=${space.name}`);
                }}
                description={space.desc}
                name={space.name}
                key={space.id}
                logo={
                  space.domain_type === 'FinancialReport'
                    ? '/models/fin_report.jpg'
                    : space.vector_type === 'KnowledgeGraph'
                      ? '/models/knowledge-graph.png'
                      : space.vector_type === 'FullText'
                        ? '/models/knowledge-full-text.jpg'
                        : '/icons/knowledge.png'
                }
                RightTop={
                  <InnerDropdown
                    menu={{
                      items: [
                        {
                          key: 'del',
                          label: (
                            <span className='text-red-400' onClick={() => showDeleteConfirm(space)}>
                              {t('Delete')}
                            </span>
                          ),
                        },
                      ],
                    }}
                  />
                }
                rightTopHover={false}
                Tags={
                  <div className='flex item-center flex-wrap gap-1'>
                    <Tag>
                      <span className='flex items-center gap-1'>
                        <ReadOutlined className='mt-[1px]' />
                        {space.docs}
                      </span>
                    </Tag>
                    <Tag>
                      <span className='flex items-center gap-1'>{space.domain_type || 'Normal'}</span>
                    </Tag>
                    {space.vector_type ? (
                      <Tag color='blue'>
                        <span className='flex items-center gap-1'>{space.vector_type}</span>
                      </Tag>
                    ) : null}
                    {space.index_methods && space.index_methods.length > 0 ? (
                      <Tag color='purple'>
                        <span className='flex items-center gap-1'>
                          {space.index_methods
                            .map(m => {
                              const map: Record<string, string> = {
                                VectorStore: t('index_vector_store'),
                                FullText: t('index_full_text'),
                                KnowledgeGraph: t('index_knowledge_graph'),
                              };
                              return map[m] || m;
                            })
                            .join('+')}
                        </span>
                      </Tag>
                    ) : null}
                    {/* Graph stats */}
                    {spaceStats[space.name]?.vertexCount != null && (
                      <Tag color='violet-inverse' className='border-violet-300 text-violet-600'>
                        <span className='flex items-center gap-0.5 text-[11px]'>
                          <NodeIndexOutlined />
                          {spaceStats[space.name].vertexCount}
                        </span>
                      </Tag>
                    )}
                    {spaceStats[space.name]?.edgeCount != null && (
                      <Tag color='violet-inverse' className='border-violet-300 text-violet-600'>
                        <span className='flex items-center gap-0.5 text-[11px]'>
                          <ShareAltOutlined />
                          {spaceStats[space.name].edgeCount}
                        </span>
                      </Tag>
                    )}
                  </div>
                }
                LeftBottom={
                  <div className='flex gap-2'>
                    <span>{space.owner}</span>
                    <span>•</span>
                    {space?.gmt_modified && <span>{moment(space?.gmt_modified).fromNow() + ' ' + t('update')}</span>}
                  </div>
                }
                RightBottom={null}
              />
            ))}
          </div>
        </div>
        <Modal
          title={t('New_knowledge_base')}
          centered
          open={isAddShow}
          destroyOnClose={true}
          onCancel={() => {
            setIsAddShow(false);
          }}
          width={1000}
          afterClose={() => {
            setActiveStep(0);
            getSpaces();
          }}
          footer={null}
        >
          {activeStep === 0 && (
            <SpaceForm
              handleStepChange={handleStepChange}
              spaceConfig={spaceConfig}
              onSuccess={() => {
                setIsAddShow(false);
                getSpaces();
                setActiveStep(0);
              }}
            />
          )}
          {activeStep === 1 && <DocTypeForm handleStepChange={handleStepChange} />}
          {activeStep === 2 && docType === 'GIT_REPO' ? (
            <GitRepoSyncForm
              spaceName={spaceName}
              onSuccess={() => {
                setIsAddShow(false);
                getSpaces();
                setActiveStep(0);
              }}
            />
          ) : (
            <DocUploadForm
              className={classNames({ hidden: activeStep !== 2 })}
              spaceName={spaceName}
              docType={docType}
              handleStepChange={handleStepChange}
            />
          )}
          {activeStep === 3 && (
            <Segmentation
              spaceName={spaceName}
              docType={docType}
              uploadFiles={files}
              handleStepChange={handleStepChange}
            />
          )}
        </Modal>
      </Spin>
    </ConstructLayout>
  );
};

export default Knowledge;
