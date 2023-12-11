import { apiInterceptors, postAgentMy, postAgentUninstall, postAgentUpload } from '@/client/api';
import { IMyPlugin } from '@/types/agent';
import { useRequest } from 'ahooks';
import { Button, Card, Spin, Tag, Tooltip, Upload, UploadProps, message } from 'antd';
import { useCallback, useState } from 'react';
import MyEmpty from '../common/MyEmpty';
import { ClearOutlined, LoadingOutlined, UploadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';

function MyPlugins() {
  const { t } = useTranslation();
  const [messageApi, contextHolder] = message.useMessage();

  const [uploading, setUploading] = useState(false);
  const [isError, setIsError] = useState(false);
  const [actionIndex, setActionIndex] = useState<number | undefined>();

  const {
    data = [],
    loading,
    refresh,
  } = useRequest(async () => {
    const [err, res] = await apiInterceptors(postAgentMy());
    setIsError(!!err);
    return res ?? [];
  });

  const uninstall = async (name: string, index: number) => {
    if (actionIndex) return;
    setActionIndex(index);
    const [err] = await apiInterceptors(postAgentUninstall(name));
    message[err ? 'error' : 'success'](err ? 'failed' : 'success');
    !err && refresh();
    setActionIndex(undefined);
  };

  const renderAction = useCallback(
    (item: IMyPlugin, index: number) => {
      if (index === actionIndex) {
        return <LoadingOutlined />;
      }
      return (
        <Tooltip title="Uninstall">
          <div
            className="w-full h-full"
            onClick={() => {
              uninstall(item.name, index);
            }}
          >
            <ClearOutlined />
          </div>
        </Tooltip>
      );
    },
    [actionIndex],
  );

  const onChange: UploadProps['onChange'] = async (info) => {
    if (!info) {
      message.error('Please select the *.zip,*.rar file');
      return;
    }
    try {
      const file = info.file;
      setUploading(true);
      const formData = new FormData();
      formData.append('doc_file', file as any);
      messageApi.open({ content: `Uploading ${file.name}`, type: 'loading', duration: 0 });
      const [err] = await apiInterceptors(postAgentUpload(undefined, formData, { timeout: 60000 }));
      if (err) return;
      message.success('success');
      refresh();
    } catch (e: any) {
      message.error(e?.message || 'Upload Error');
    } finally {
      setUploading(false);
      messageApi.destroy();
    }
  };

  return (
    <Spin spinning={loading}>
      {contextHolder}
      <div>
        <Upload
          disabled={loading}
          className="mr-1"
          beforeUpload={() => false}
          name="file"
          accept=".zip,.rar"
          multiple={false}
          onChange={onChange}
          showUploadList={{
            showDownloadIcon: false,
            showPreviewIcon: false,
            showRemoveIcon: false,
          }}
          itemRender={() => <></>}
        >
          <Button loading={uploading} type="primary" icon={<UploadOutlined />}>
            {t('Upload')}
          </Button>
        </Upload>
      </div>
      {!data.length && !loading && <MyEmpty error={isError} refresh={refresh} />}
      <div className="flex gap-2 md:gap-4">
        {data.map((item, index) => (
          <Card className="w-full md:w-1/2 lg:w-1/3 xl:w-1/4" key={item.id} actions={[renderAction(item, index)]}>
            <Tooltip title={item.name}>
              <h2 className="mb-2 text-base font-semibold line-clamp-1">{item.name}</h2>
            </Tooltip>
            {item.version && <Tag>v{item.version}</Tag>}
            {item.type && <Tag>Type {item.type}</Tag>}
            <Tooltip title={item.description}>
              <p className="mt-2 line-clamp-2 text-gray-400 text-sm">{item.description}</p>
            </Tooltip>
          </Card>
        ))}
      </div>
    </Spin>
  );
}

export default MyPlugins;
