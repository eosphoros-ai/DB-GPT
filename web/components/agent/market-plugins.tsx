import { apiInterceptors, postAgentHubUpdate, postAgentInstall, postAgentQuery, postAgentUninstall } from '@/client/api';
import { IAgentPlugin, PostAgentQueryParams } from '@/types/agent';
import { useRequest } from 'ahooks';
import { Button, Card, Form, Input, Spin, Tag, Tooltip, message } from 'antd';
import { useCallback, useMemo, useState } from 'react';
import MyEmpty from '../common/MyEmpty';
import { ClearOutlined, DownloadOutlined, GithubOutlined, LoadingOutlined, SearchOutlined, SyncOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

function MarketPlugins() {
  const { t } = useTranslation();

  const [uploading, setUploading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [actionIndex, setActionIndex] = useState<number | undefined>();

  const [form] = Form.useForm<PostAgentQueryParams['filter']>();

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
  } = useRequest(async () => {
    const queryParams: PostAgentQueryParams = {
      page_index: pagination.pageNo,
      page_size: pagination.pageSize,
      filter: form.getFieldsValue(),
    };
    const [err, res] = await apiInterceptors(postAgentQuery(queryParams));
    setIsError(!!err);
    return res?.datas ?? [];
  });

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

  const renderAction = useCallback(
    (agent: IAgentPlugin, index: number) => {
      if (index === actionIndex) {
        return <LoadingOutlined />;
      }
      return agent.installed ? (
        <Tooltip title="Uninstall">
          <div
            className="w-full h-full"
            onClick={() => {
              pluginAction(agent.name, index, false);
            }}
          >
            <ClearOutlined />
          </div>
        </Tooltip>
      ) : (
        <Tooltip title="Install">
          <div
            className="w-full h-full"
            onClick={() => {
              pluginAction(agent.name, index, true);
            }}
          >
            <DownloadOutlined />
          </div>
        </Tooltip>
      );
    },
    [actionIndex, pluginAction],
  );

  return (
    <Spin spinning={loading}>
      <Form form={form} layout="inline" onFinish={refresh} className="mb-2">
        <Form.Item className="!mb-2" name="name" label={'Name'}>
          <Input allowClear className="w-48" />
        </Form.Item>
        <Form.Item>
          <Button className="mr-2" type="primary" htmlType="submit" icon={<SearchOutlined />}>
            {t('Search')}
          </Button>
          <Button loading={uploading} type="primary" icon={<SyncOutlined />} onClick={updateFromGithub}>
            {t('Update_From_Github')}
          </Button>
        </Form.Item>
      </Form>
      {!agents.length && !loading && <MyEmpty error={isError} refresh={refresh} />}
      <div className="flex flex-wrap gap-2 md:gap-4">
        {agents.map((agent, index) => (
          <Card
            className="w-full md:w-1/2 lg:w-1/3 xl:w-1/4"
            key={agent.id}
            actions={[
              renderAction(agent, index),
              <Tooltip key="github" title="Github">
                <div
                  className="w-full h-full"
                  onClick={() => {
                    window.open(agent.storage_url, '_blank');
                  }}
                >
                  <GithubOutlined />
                </div>
              </Tooltip>,
            ]}
          >
            <Tooltip title={agent.name}>
              <h2 className="mb-2 text-base font-semibold line-clamp-1">{agent.name}</h2>
            </Tooltip>
            {agent.author && <Tag>{agent.author}</Tag>}
            {agent.version && <Tag>v{agent.version}</Tag>}
            {agent.type && <Tag>Type {agent.type}</Tag>}
            {agent.storage_channel && <Tag>{agent.storage_channel}</Tag>}
            <Tooltip title={agent.description}>
              <p className="mt-2 line-clamp-2 text-gray-400 text-sm">{agent.description}</p>
            </Tooltip>
          </Card>
        ))}
      </div>
    </Spin>
  );
}

export default MarketPlugins;
