/* eslint-disable react-hooks/rules-of-hooks */
import { metadataBatch } from '@/client/api';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd';
import { Button, Upload, message } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

type Props = {
  formValuesChange: any;
  data: IFlowNodeParameter;
  onChange?: (value: any) => void;
};
export const renderUpload = (params: Props) => {
  const { t } = useTranslation();
  const urlList = useRef<string[]>([]);
  const { data, formValuesChange } = params;
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  // 获取上传文件元数据
  useEffect(() => {
    if (data.value) {
      let uris: string[] = [];
      typeof data.value === 'string' ? uris.push(data.value) : (uris = data.value);
      const parameter: any = {
        uris,
      };
      metadataBatch(parameter)
        .then(res => {
          const urlList: UploadFile[] = [];
          for (let index = 0; index < res.data.data.length; index++) {
            const element = res.data.data[index];
            urlList.push({
              uid: element.file_id,
              name: element.file_name,
              status: 'done',
              url: element.uri,
            });
          }
          setFileList(urlList);
        })
        .catch(error => {
          console.log(error);
        });
    }
  }, []);

  const attr = convertKeysToCamelCase(data.ui?.attr || {});
  const [uploading, setUploading] = useState(false);
  const [uploadType, setUploadType] = useState('');
  const getUploadSuccessUrl = (url: string) => {
    if (urlList.current.length === data.ui.attr.max_count) {
      urlList.current.pop();
    }
    urlList.current.push(url);
    if (data.ui.attr.max_count === 1) {
      formValuesChange({ [data.name]: urlList.current.toString() });
    } else {
      formValuesChange({ [data.name]: urlList.current });
    }
  };

  const handleFileRemove = (file: any) => {
    const index = urlList.current.indexOf(file.response.data[0].uri);
    if (index !== -1) {
      urlList.current.splice(index, 1);
    }
    setUploading(false);
    if (data.ui.attr.max_count === 1) {
      formValuesChange({ [data.name]: urlList.current.toString() });
    } else {
      formValuesChange({ [data.name]: urlList.current });
    }
  };

  const props: UploadProps = {
    name: 'files',
    action: process.env.API_BASE_URL ?? '' + data.ui.action,
    headers: {
      authorization: 'authorization-text',
    },
    defaultFileList: fileList,
    onChange(info) {
      setUploading(true);
      if (info.file.status !== 'uploading') {
        setUploading(false);
      }
      if (info.file.status === 'done') {
        setUploading(false);
        message.success(`${info.file.response.data[0].file_name} ${t('Upload_Data_Successfully')}`);
        getUploadSuccessUrl(info.file.response.data[0].uri);
      } else if (info.file.status === 'error') {
        setUploading(false);
        message.error(`${info.file.response.data[0].file_name}  ${t('Upload_Data_Failed')}`);
      }
    },
  };

  if (!uploadType && data.ui?.file_types && Array.isArray(data.ui?.file_types)) {
    setUploadType(data.ui?.file_types.toString());
  }

  return (
    <div className='p-2 text-sm text-center'>
      <Upload
        onRemove={handleFileRemove}
        {...props}
        {...attr}
        multiple={data.is_list ? true : false}
        accept={uploadType}
      >
        <Button loading={uploading} icon={<UploadOutlined />}>
          {t('Upload_Data')}
        </Button>
      </Upload>
    </div>
  );
};
