import {
  apiInterceptors,
  postDbgptsHubUpdate,
  postDbgptsInstall,
  postDbgptsMy,
  postDbgptsQuery,
  postDbgptsUninstall,
} from '@/client/api';
import BlurredCard, { ChatButton } from '@/new-components/common/blurredCard';
import ConstructLayout from '@/new-components/layout/Construct';
import { IAgentPlugin, PostAgentQueryParams } from '@/types/agent';
import { ClearOutlined, DownloadOutlined, SearchOutlined, SyncOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Button, Input, Segmented, SegmentedProps, Spin, Tag, message } from 'antd';
import cls from 'classnames';
import moment from 'moment';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
function Agent() {
  const { t } = useTranslation();

  const [searchValue, setSearchValue] = useState('');
  const [activeKey, setActiveKey] = useState<string>('market');
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [_error, setIsError] = useState(false); // _error is not used
  const [actionIndex, setActionIndex] = useState<number | undefined>();
  const [typeStr, setTypeStr] = useState('all');

  const pagination = useMemo<{ pageNo: number; pageSize: number }>(
    () => ({
      pageNo: 1,
      pageSize: 20,
    }),
    [],
  );

  const { data: agents = [], refresh } = useRequest<IAgentPlugin[], []>(
    async () => {
      setLoading(true);
      if (activeKey === 'my') {
        const [err, res] = await apiInterceptors(
          postDbgptsMy({
            name: searchValue || undefined,
            type: typeStr === 'all' ? undefined : typeStr,
            page_index: pagination.pageNo,
            page_size: pagination.pageSize,
          }),
        );
        setLoading(false);
        setIsError(!!err);
        return res?.items ?? [];
      }
      const queryParams: PostAgentQueryParams = {
        page_index: pagination.pageNo,
        page_size: pagination.pageSize,
        name: searchValue || undefined,
        type: typeStr === 'all' ? undefined : typeStr,
      };
      const [err, res] = await apiInterceptors(postDbgptsQuery(queryParams));
      setLoading(false);
      setIsError(!!err);
      return res?.items ?? [];
    },
    {
      manual: true,
    },
  );

  const updateFromGithub = async () => {
    try {
      setUploading(true);
      const [err] = await apiInterceptors(postDbgptsHubUpdate());
      if (err) return;
      message.success('success');
      refresh();
    } finally {
      setUploading(false);
    }
  };
  useEffect(() => {
    refresh();
  }, [activeKey, typeStr]);

  const pluginAction = useCallback(
    async (agent: { name: string; type: string }, index: number, isInstall: boolean) => {
      if (actionIndex) return;
      setActionIndex(index);
      setLoading(true);
      let errs = null;
      if (isInstall) {
        const [err] = await apiInterceptors(postDbgptsInstall(agent));
        errs = err;
      } else {
        const [err] = await apiInterceptors(
          postDbgptsUninstall({
            name: agent.name,
            type: agent.type,
          }),
        );
        errs = err;
      }
      setLoading(false);
      if (!errs) {
        message.success('success');
        refresh();
      }
      setActionIndex(undefined);
    },
    [actionIndex, refresh],
  );
  const items: SegmentedProps['options'] = [
    {
      value: 'market',
      label: t('community_dbgpts'),
    },
    {
      value: 'my',
      label: t('my_dbgpts'),
    },
  ];

  const typeItems: SegmentedProps['options'] = [
    {
      value: 'all',
      label: t('All'),
    },
    {
      value: 'workflow',
      label: t('workflow'),
    },
    {
      value: 'agents',
      label: 'Agent',
    },
    {
      value: 'resources',
      label: t('resources'),
    },
    {
      value: 'apps',
      label: t('app'),
    },
    {
      value: 'operators',
      label: t('operators'),
    },
  ];

  const logoFn = (type: string) => {
    switch (type) {
      case 'workflow':
        return '/pictures/flow.png';
      case 'resources':
        return '/pictures/database.png';
      case 'apps':
        return '/pictures/app.png';
      case 'operators':
        return '/pictures/knowledge.png';
      case 'agents':
      default:
        return '/pictures/agent.png';
    }
  };

  return (
    <ConstructLayout>
      <Spin spinning={loading}>
        <div className='h-screen w-full p-4 md:p-6 overflow-y-auto'>
          <div className='flex justify-between items-center mb-6'>
            <div className='flex items-center gap-4'>
              <Segmented
                className='backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 border-2 border-white rounded-lg shadow p-1 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
                options={items}
                onChange={key => {
                  setActiveKey(key as string);
                }}
                value={activeKey}
              />
              {/* <Input
                variant="filled"
                prefix={<SearchOutlined />}
                placeholder={t('please_enter_the_keywords')}
                value={searchValue}
                onChange={(e) => setSearchValue(e.target.value)}
                onPressEnter={refresh}
                allowClear
                className="w-[230px] h-[40px] border-1 border-white backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60"
              /> */}
            </div>
            <div className='flex items-center gap-4'>
              <Button
                className={cls('border-none text-white bg-button-gradient h-full', {
                  'opacity-40': false,
                })}
                loading={uploading}
                icon={<SyncOutlined />}
                onClick={updateFromGithub}
              >
                {t('Refresh_dbgpts')}
              </Button>
            </div>
          </div>
          <div className='w-full flex flex-wrap pb-12 mx-[-8px]'>
            <Segmented
              className='backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 border-2 border-white rounded-lg shadow p-1 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
              options={typeItems}
              onChange={key => {
                setTypeStr(key as string);
              }}
              value={typeStr}
            />
            <Input
              variant='filled'
              prefix={<SearchOutlined />}
              placeholder={t('please_enter_the_keywords')}
              value={searchValue}
              onChange={e => setSearchValue(e.target.value)}
              onPressEnter={refresh}
              allowClear
              className='w-[230px] h-[40px] border-1 border-white ml-4 backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
            />
          </div>
          <div className='flex flex-wrap pb-12'>
            {agents.map((agent, index) => (
              <BlurredCard
                logo={logoFn(agent.type)}
                onClick={() => {
                  window.open(`https://github.com/eosphoros-ai/dbgpts/tree/main/${agent.type}/${agent.name}`, '_blank');
                }}
                description={agent.description}
                name={agent.name}
                key={agent.id}
                Tags={
                  <div>
                    {agent.author && <Tag>{agent.author}</Tag>}
                    {agent.version && <Tag>v{agent.version}</Tag>}
                    {/* {agent.type && <Tag>Type {agent.type}</Tag>} */}
                    {agent.storage_channel && <Tag>{agent.storage_channel}</Tag>}
                  </div>
                }
                LeftBottom={
                  <div className='flex gap-2'>
                    {agent.author && <span>{agent.author}</span>}
                    {agent.author && <span>•</span>}
                    {agent?.gmt_created && <span>{moment(agent?.gmt_created).fromNow() + ' ' + t('update')}</span>}
                  </div>
                }
                RightTop={agent.type && <Tag>{agent.type}</Tag>}
                rightTopHover={false}
                RightBottom={
                  agent.installed || activeKey == 'my' ? (
                    <ChatButton
                      Icon={<ClearOutlined />}
                      text='Uninstall'
                      onClick={() => {
                        pluginAction(agent, index, false);
                      }}
                    />
                  ) : (
                    <ChatButton
                      Icon={<DownloadOutlined />}
                      text='Install'
                      onClick={() => {
                        pluginAction(agent, index, true);
                      }}
                    />
                  )
                }
              />
            ))}
          </div>
          {/* {activeKey !== 'market' ? <MyPlugins /> : <MarketPlugins />} */}
        </div>
      </Spin>
    </ConstructLayout>
  );
}

export default Agent;
