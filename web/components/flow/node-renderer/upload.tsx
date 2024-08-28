import React, { useState, useRef } from 'react';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { Button, Upload, message,Form } from 'antd';
import { convertKeysToCamelCase } from '@/utils/flow';
import { IFlowNodeParameter } from '@/types/flow';
import { useTranslation } from 'react-i18next';

type Props = {
  formValuesChange:any,
  data: IFlowNodeParameter;
  onChange?: (value: any) => void;
};
export const renderUpload = (params: Props) => {
  const { t } = useTranslation();
  const urlList = useRef<string[]>([]);
  const { data ,formValuesChange} = params;
  const form = Form.useFormInstance()

  const attr = convertKeysToCamelCase(data.ui?.attr || {});
  const [uploading, setUploading] = useState(false);
  const [uploadType, setUploadType] = useState('');

  const getUploadSuccessUrl = (url: string) => {
    if (urlList.current.length === data.ui.attr.max_count) {
      urlList.current.pop();
    }
    urlList.current.push(url);
    if (data.ui.attr.max_count === 1) {
      formValuesChange({file:urlList.current.toString()},{force:true})
    }else{
      formValuesChange({multiple_files:JSON.stringify(urlList.current)},{force:true})
    }
  };

  const handleFileRemove = (file: any) => {
    const index = urlList.current.indexOf(file.response.data[0].uri);
    if (index !== -1) {
      urlList.current.splice(index, 1);
    }
    if (data.ui.attr.max_count === 1) {
      formValuesChange({file:urlList.current.toString()},{force:true})
    }else{
      formValuesChange({multiple_files:JSON.stringify(urlList.current)},{force:true})
    }
  };

  const props: UploadProps = {
    name: 'files',
    action: process.env.API_BASE_URL + data.ui.action,
    headers: {
      authorization: 'authorization-text',
    },
    onChange(info) {
      setUploading(true);
      if (info.file.status !== 'uploading') {
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
    <div className="p-2 text-sm text-center">
      {data.is_list ? (
        <Upload onRemove={handleFileRemove} {...props} {...attr} multiple={true} accept={uploadType}>
          <Button loading={uploading} icon={<UploadOutlined />}>
            {t('Upload_Data')}
          </Button>
        </Upload>
      ) : (
        <Upload onRemove={handleFileRemove} {...props} {...attr} multiple={false} accept={uploadType}>
          <Button loading={uploading} icon={<UploadOutlined />}>
            {t('Upload_Data')}
          </Button>
        </Upload>
      )}
    </div>
  );
};