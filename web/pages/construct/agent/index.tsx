import {
  apiInterceptors,
  postAgentHubUpdate,
  postAgentInstall,
  postAgentMy,
  postAgentQuery,
  postAgentUninstall,
} from '@/client/api';
import BlurredCard, { ChatButton } from '@/new-components/common/blurredCard';
import ConstructLayout from '@/new-components/layout/Construct';
import { IAgentPlugin, PostAgentQueryParams } from '@/types/agent';
import { ClearOutlined, DownloadOutlined, SyncOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import { Button, Segmented, SegmentedProps, Spin, Tag, message } from 'antd';
import cls from 'classnames';
import moment from 'moment';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
// import MyPlugins from '@/components/agent/my-plugins';
// import MarketPlugins from '@/components/agent/market-plugins';

function Agent() {
  const { t } = useTranslation();

  const [searchValue] = useState('');
  const [activeKey, setActiveKey] = useState<string>('market');
  const [uploading, setUploading] = useState(false);
  const [_, setIsError] = useState(false);
  const [actionIndex, setActionIndex] = useState<number | undefined>();

  const pagination = useMemo<{ pageNo: number; pageSize: number }>(
    () => ({
      pageNo: 1,
      pageSize: 20,
    }),
    [],
  );

  const {
    data: agents = [],
    loading,
    refresh,
  } = useRequest<IAgentPlugin[], []>(
    async () => {
      if (activeKey === 'my') {
        const [err, res] = await apiInterceptors(postAgentMy());
        setIsError(!!err);
        return res ?? [];
      }
      const queryParams: PostAgentQueryParams = {
        page_index: pagination.pageNo,
        page_size: pagination.pageSize,
        filter: {
          name: searchValue || undefined,
        },
      };
      const [err, res] = await apiInterceptors(postAgentQuery(queryParams));
      setIsError(!!err);
      return res?.datas ?? [];
    },
    {
      manual: true,
    },
  );

  const updateFromGithub = async () => {
    try {
      setUploading(true);
      const [err] = await apiInterceptors(postAgentHubUpdate());
      if (err) return;
      message.success('success');
      refresh();
    } finally {
      setUploading(false);
    }
  };
  useEffect(() => {
    refresh();
  }, [activeKey]);
  const pluginAction = useCallback(
    async (name: string, index: number, isInstall: boolean) => {
      if (actionIndex) return;
      setActionIndex(index);
      const [err] = await apiInterceptors((isInstall ? postAgentInstall : postAgentUninstall)(name));
      if (!err) {
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
      label: t('Market_Plugins'),
    },
    {
      value: 'my',
      label: t('My_Plugins'),
    },
  ];

  return (
    <ConstructLayout>
      <div className='px-6'>
        <Spin spinning={loading}>
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
                {t('Update_From_Github')}
              </Button>
            </div>
          </div>
          {agents.map((agent, index) => (
            <BlurredCard
              logo='/pictures/agent.png'
              onClick={() => {
                if (agent.storage_url) window.open(agent.storage_url, '_blank');
              }}
              description={agent.description}
              name={agent.name}
              key={agent.id}
              Tags={
                <div>
                  {agent.author && <Tag>{agent.author}</Tag>}
                  {agent.version && <Tag>v{agent.version}</Tag>}
                  {agent.type && <Tag>Type {agent.type}</Tag>}
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
              RightBottom={
                agent.installed || activeKey == 'my' ? (
                  <ChatButton
                    Icon={<ClearOutlined />}
                    text='Uninstall'
                    onClick={() => {
                      pluginAction(agent.name, index, false);
                    }}
                  />
                ) : (
                  <ChatButton
                    Icon={<DownloadOutlined />}
                    text='Install'
                    onClick={() => {
                      pluginAction(agent.name, index, true);
                    }}
                  />
                )
              }
            />
          ))}
          {/* {activeKey !== 'market' ? <MyPlugins /> : <MarketPlugins />} */}
        </Spin>
      </div>
    </ConstructLayout>
  );
}

export default Agent;
