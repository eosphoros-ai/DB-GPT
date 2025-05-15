import { apiInterceptors, postChatModeParamsFileLoad, postChatModeParamsList } from '@/client/api';
import DBIcon from '@/components/common/db-icon';
import { ChatContentContext } from '@/pages/chat';
import { IDB } from '@/types/chat';
import { dbMapper } from '@/utils';
import { ExperimentOutlined, FolderAddOutlined } from '@ant-design/icons';
import { useAsyncEffect, useRequest } from 'ahooks';
import type { UploadFile } from 'antd';
import { Select, Tooltip, Upload } from 'antd';
import classNames from 'classnames';
import { useSearchParams } from 'next/navigation';
import React, { memo, useCallback, useContext, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

const Resource: React.FC<{
  fileList: UploadFile[];
  setFileList: React.Dispatch<React.SetStateAction<UploadFile<any>[]>>;
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
  fileName: string;
}> = ({ fileList, setFileList, setLoading, fileName }) => {
  const { setResourceValue, appInfo, refreshHistory, refreshDialogList, modelValue, resourceValue } =
    useContext(ChatContentContext);

  const { temperatureValue, maxNewTokensValue } = useContext(ChatContentContext);
  const searchParams = useSearchParams();
  const scene = searchParams?.get('scene') ?? '';
  const chatId = searchParams?.get('id') ?? '';

  const { t } = useTranslation();

  // dataBase
  const [dbs, setDbs] = useState<IDB[]>([]);

  // 左边工具栏动态可用key
  const paramKey: string[] = useMemo(() => {
    return appInfo.param_need?.map(i => i.type) || [];
  }, [appInfo.param_need]);

  const isDataBase = useMemo(() => {
    return (
      paramKey.includes('resource') && appInfo.param_need?.filter(i => i.type === 'resource')[0]?.value === 'database'
    );
  }, [appInfo.param_need, paramKey]);

  const isKnowledge = useMemo(() => {
    return (
      paramKey.includes('resource') && appInfo.param_need?.filter(i => i.type === 'resource')[0]?.value === 'knowledge'
    );
  }, [appInfo.param_need, paramKey]);

  const resource = useMemo(() => appInfo.param_need?.find(i => i.type === 'resource'), [appInfo.param_need]);

  // 获取db
  const { run, loading } = useRequest(async () => await apiInterceptors(postChatModeParamsList(scene as string)), {
    manual: true,
    onSuccess: data => {
      const [, res] = data;
      setDbs(res ?? []);
    },
  });

  useAsyncEffect(async () => {
    if ((isDataBase || isKnowledge) && !resource?.bind_value) {
      await run();
    }
  }, [isDataBase, isKnowledge, resource]);

  const dbOpts = useMemo(
    () =>
      dbs.map?.((db: IDB) => {
        return {
          label: (
            <>
              <DBIcon
                width={24}
                height={24}
                src={dbMapper[db.type].icon}
                label={dbMapper[db.type].label}
                className='w-[1.5em] h-[1.5em] mr-1 inline-block mt-[-4px]'
              />
              {db.param}
            </>
          ),
          value: db.param,
        };
      }),
    [dbs],
  );

  // 上传
  const onUpload = useCallback(async () => {
    const formData = new FormData();
    formData.append('doc_files', fileList?.[0] as any);
    setLoading(true);
    const [_, res] = await apiInterceptors(
      postChatModeParamsFileLoad({
        convUid: chatId,
        chatMode: scene,
        data: formData,
        model: modelValue,
        temperatureValue,
        maxNewTokensValue,
        config: {
          timeout: 1000 * 60 * 60,
        },
      }),
    ).finally(() => {
      setLoading(false);
    });
    if (res) {
      setResourceValue(res);
      await refreshHistory();
      await refreshDialogList();
    }
  }, [chatId, fileList, modelValue, refreshDialogList, refreshHistory, scene, setLoading, setResourceValue]);

  if (!paramKey.includes('resource')) {
    return (
      <Tooltip title={t('extend_tip')}>
        <div className='flex w-8 h-8 items-center justify-center rounded-md hover:bg-[rgb(221,221,221,0.6)]'>
          <ExperimentOutlined className='text-lg cursor-not-allowed opacity-30' />
        </div>
      </Tooltip>
    );
  }

  switch (resource?.value) {
    case 'excel_file':
    case 'text_file':
    case 'image_file':
    case 'audio_file':
    case 'video_file': {
      // Dynamically set accept attribute based on resource type
      const getAcceptTypes = () => {
        switch (resource?.value) {
          case 'excel_file':
            return '.csv,.xlsx,.xls';
          case 'text_file':
            return '.txt,.doc,.docx,.pdf,.md';
          case 'image_file':
            return '.jpg,.jpeg,.png,.gif,.bmp,.webp';
          case 'audio_file':
            return '.mp3,.wav,.ogg,.aac';
          case 'video_file':
            return '.mp4,.wav,.wav';
          default:
            return '';
        }
      };
      // Only disable file upload when scene is "chat_excel", otherwise allow modification
      const isDisabled = scene === 'chat_excel' ? !!fileName || !!fileList[0]?.name : false;
      const title = scene === 'chat_excel' ? t('file_tip') : t('file_upload_tip');

      return (
        <Upload
          name='file'
          accept={getAcceptTypes()}
          fileList={fileList}
          showUploadList={false}
          beforeUpload={(_, fileList) => {
            setFileList?.(fileList);
          }}
          customRequest={onUpload}
          disabled={isDisabled}
        >
          <Tooltip title={title} arrow={false} placement='bottom'>
            <div className='flex w-8 h-8 items-center justify-center rounded-md hover:bg-[rgb(221,221,221,0.6)]'>
              <FolderAddOutlined className={classNames('text-xl', { 'cursor-pointer': !isDisabled })} />
            </div>
          </Tooltip>
        </Upload>
      );
    }
    case 'database':
    case 'knowledge':
    case 'plugin':
    case 'awel_flow':
      if (!resourceValue) {
        setResourceValue(dbOpts?.[0]?.value);
      }
      return (
        <Select
          value={resourceValue}
          className='w-52 h-8 rounded-3xl'
          onChange={val => {
            setResourceValue(val);
          }}
          disabled={!!resource?.bind_value}
          loading={loading}
          options={dbOpts}
        />
      );
  }
};

export default memo(Resource);
