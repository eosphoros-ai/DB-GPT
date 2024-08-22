import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, getUsableModels } from '@/client/api';
import { MODEL_ICON_MAP } from '@/utils/constants';
import { useRequest } from 'ahooks';
import { Select } from 'antd';
import Image from 'next/image';
import React, { useContext, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CaretDownOutlined } from '@ant-design/icons';

import styles from './styles.module.css';

const DEFAULT_ICON_URL = '/models/huggingface.svg';

export function renderModelIcon(model?: string, props?: { width: number; height: number }) {
  const { width, height } = props || {};

  if (!model) return null;

  return (
    <Image
      className="rounded-full border border-gray-200 object-contain bg-white inline-block"
      width={width || 24}
      height={height || 24}
      src={MODEL_ICON_MAP[model]?.icon || DEFAULT_ICON_URL}
      alt="llm"
    />
  );
}

const ModelSelector: React.FC = () => {
  const { t } = useTranslation();
  const { model, setModel } = useContext(ChatContext);

  const [modelList, setModelList] = useState<string[]>([]);

  useRequest(async () => await apiInterceptors(getUsableModels()), {
    onSuccess: (data) => {
      const [, res] = data;
      setModelList(res || []);
    },
  });

  if (modelList.length === 0) {
    return null;
  }

  return (
    <div className={styles['cus-selector']}>
      <Select
        value={model}
        placeholder={t('choose_model')}
        className="w-48 h-8 rounded-3xl"
        suffixIcon={<CaretDownOutlined className="text-sm text-[#000000]" />}
        onChange={(val) => {
          setModel(val);
        }}
      >
        {modelList.map((item) => (
          <Select.Option key={item}>
            <div className="flex items-center">
              {renderModelIcon(item)}
              <span className="ml-2">{MODEL_ICON_MAP[item]?.label || item}</span>
            </div>
          </Select.Option>
        ))}
      </Select>
    </div>
  );
};

export default ModelSelector;
