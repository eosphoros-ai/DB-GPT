import { apiInterceptors, postChatModeParamsFileLoad } from '@/client/api';
import { dbMapper } from '@/utils';
import { FolderAddOutlined, LoadingOutlined, SwapOutlined } from '@ant-design/icons';
import { useRequest } from 'ahooks';
import type { MenuProps } from 'antd';
import { Dropdown, Spin, Upload } from 'antd';
import React, { useContext, useMemo, useState } from 'react';
import { MobileChatContext } from '../';
import OptionIcon from './OptionIcon';

const Resource: React.FC = () => {
  const { appInfo, resourceList, scene, model, conv_uid, getChatHistoryRun, setResource, resource } =
    useContext(MobileChatContext);

  const [selectedVal, setSelectedVal] = useState<any>(null);

  // 资源类型
  const resourceVal = useMemo(() => {
    return appInfo?.param_need?.filter(item => item.type === 'resource')?.[0]?.value;
  }, [appInfo]);

  const items: MenuProps['items'] = useMemo(() => {
    if (resourceList && resourceList.length > 0) {
      return resourceList.map(item => {
        return {
          label: (
            <div
              className='flex items-center gap-2'
              onClick={() => {
                setSelectedVal(item);
                setResource(item.space_id || item.param);
              }}
            >
              <OptionIcon width={14} height={14} src={dbMapper[item.type].icon} label={dbMapper[item.type].label} />
              <span className='text-xs'>{item.param}</span>
            </div>
          ),
          key: item.space_id || item.param,
        };
      });
    }
    return [];
  }, [resourceList, setResource]);

  // 上传文件
  const { run: uploadFile, loading } = useRequest(
    async formData => {
      const [, res] = await apiInterceptors(
        postChatModeParamsFileLoad({
          convUid: conv_uid,
          chatMode: scene,
          data: formData,
          model,
          config: {
            timeout: 1000 * 60 * 60,
          },
        }),
      );
      setResource(res);
      return res;
    },
    {
      manual: true,
      onSuccess: async () => {
        await getChatHistoryRun();
      },
    },
  );

  // 上传文件变化
  const handleFileChange = async (info: any) => {
    const formData = new FormData();
    formData.append('doc_file', info?.file);
    await uploadFile(formData);
  };

  // 上传文件展示内容
  const uploadContent = useMemo(() => {
    if (loading) {
      return (
        <div className='flex items-center gap-1'>
          <Spin size='small' indicator={<LoadingOutlined spin />} />
          <span className='text-xs'>上传中</span>
        </div>
      );
    }
    if (resource) {
      return (
        <div className='flex gap-1'>
          <span className='text-xs'>{resource.file_name}</span>
          <SwapOutlined rotate={90} />
        </div>
      );
    }
    return (
      <div className='flex items-center gap-1'>
        <FolderAddOutlined className='text-base' />
        <span className='text-xs'>上传文件</span>
      </div>
    );
  }, [loading, resource]);

  const renderContent = () => {
    switch (resourceVal) {
      case 'excel_file':
      case 'text_file':
      case 'image_file':
        return (
          <div className='flex items-center justify-center gap-1 border rounded-xl bg-white dark:bg-black px-2 flex-shrink-0'>
            <Upload
              name='file'
              accept='.xlsx,.xls'
              maxCount={1}
              showUploadList={false}
              beforeUpload={() => false}
              onChange={handleFileChange}
              className='flex h-full w-full items-center justify-center'
            >
              {uploadContent}
            </Upload>
          </div>
        );
      case 'database':
      case 'knowledge':
      case 'plugin':
      case 'awel_flow':
        if (!resourceList?.length) {
          return null;
        }
        return (
          <Dropdown
            menu={{
              items,
            }}
            placement='top'
            trigger={['click']}
          >
            <div className='flex items-center gap-1 border rounded-xl bg-white dark:bg-black p-2 flex-shrink-0'>
              <OptionIcon
                width={14}
                height={14}
                src={dbMapper[selectedVal?.type || resourceList?.[0]?.type]?.icon}
                label={dbMapper[selectedVal?.type || resourceList?.[0]?.type]?.label}
              />
              <span className='text-xs font-medium'>{selectedVal?.param || resourceList?.[0]?.param}</span>
              <SwapOutlined rotate={90} />
            </div>
          </Dropdown>
        );
    }
  };
  return <>{renderContent()}</>;
};

export default Resource;
