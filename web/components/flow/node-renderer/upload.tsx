import React from 'react';
import { UploadOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { Button, Upload } from 'antd';
import { convertKeysToCamelCase } from '@/utils/flow';
import { IFlowNodeParameter } from '@/types/flow';
import { useTranslation } from 'react-i18next';

const props: UploadProps = {
  name: 'file',
  action: 'https://660d2bd96ddfa2943b33731c.mockapi.io/api/upload',
  headers: {
    authorization: 'authorization-text',
  },
};

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderUpload = (params: Props) => {
  const { t } = useTranslation();

  const { data, defaultValue, onChange } = params;

  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <div className="p-2 text-sm text-center">
      <Upload {...attr}   {...props}>
        <Button icon={<UploadOutlined />}>{t('UploadData')}</Button>
      </Upload>
    </div>
  )


}

