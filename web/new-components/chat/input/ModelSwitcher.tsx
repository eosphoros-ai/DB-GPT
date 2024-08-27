import { ChatContext } from '@/app/chat-context';
import { ChatContentContext } from '@/pages/chat';
import { SettingOutlined } from '@ant-design/icons';
import { Select, Tooltip } from 'antd';
import React, { memo, useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

import ModelIcon from '../content/ModelIcon';

const ModelSwitcher: React.FC = () => {
  const { modelList } = useContext(ChatContext);
  const { appInfo, modelValue, setModelValue } = useContext(ChatContentContext);

  const { t } = useTranslation();

  // 左边工具栏动态可用key
  const paramKey: string[] = useMemo(() => {
    return appInfo.param_need?.map((i) => i.type) || [];
  }, [appInfo.param_need]);

  if (!paramKey.includes('model')) {
    return (
      <Tooltip title={t('model_tip')}>
        <div className="flex w-8 h-8 items-center justify-center rounded-md hover:bg-[rgb(221,221,221,0.6)]">
          <SettingOutlined className="text-xl cursor-not-allowed opacity-30" />
        </div>
      </Tooltip>
    );
  }

  return (
    <Select
      value={modelValue}
      placeholder={t('choose_model')}
      className="h-8 rounded-3xl"
      onChange={(val) => {
        setModelValue(val);
      }}
      popupMatchSelectWidth={300}
    >
      {modelList.map((item) => (
        <Select.Option key={item}>
          <div className="flex items-center">
            <ModelIcon model={item} />
            <span className="ml-2">{item}</span>
          </div>
        </Select.Option>
      ))}
    </Select>
  );
};

export default memo(ModelSwitcher);
