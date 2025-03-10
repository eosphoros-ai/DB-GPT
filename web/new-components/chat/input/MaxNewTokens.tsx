import { ChatContentContext } from '@/pages/chat';
import { ControlOutlined } from '@ant-design/icons';
import { InputNumber, Popover, Slider, Tooltip } from 'antd';
import React, { memo, useContext, useMemo } from 'react';
import { useTranslation } from 'react-i18next';

const MaxNewTokens: React.FC<{
  maxNewTokensValue: number;
  setMaxNewTokensValue: (value: number) => void;
}> = ({ maxNewTokensValue, setMaxNewTokensValue }) => {
  const { appInfo } = useContext(ChatContentContext);
  const { t } = useTranslation();

  const paramKey: string[] = useMemo(() => {
    return appInfo.param_need?.map(i => i.type) || [];
  }, [appInfo.param_need]);

  if (!paramKey.includes('max_new_tokens')) {
    return (
      <Tooltip title={t('max_new_tokens_tip')}>
        <div className='flex w-8 h-8 items-center justify-center rounded-md hover:bg-[rgb(221,221,221,0.6)] cursor-pointer'>
          <ControlOutlined className='text-xl cursor-not-allowed opacity-30' />
        </div>
      </Tooltip>
    );
  }

  // 处理 InputNumber 的值变化
  const handleInputChange = (value: number | null) => {
    if (value === null || isNaN(value)) {
      return;
    }
    setMaxNewTokensValue(value);
  };

  // 处理 Slider 的值变化
  const handleSliderChange = (value: number) => {
    setMaxNewTokensValue(value);
  };

  return (
    <div className='flex items-center'>
      <Popover
        arrow={false}
        trigger={['click']}
        placement='topLeft'
        content={() => (
          <div className='flex items-center gap-2'>
            <Slider
              className='w-32'
              min={1}
              max={20480}
              step={1}
              onChange={handleSliderChange}
              value={typeof maxNewTokensValue === 'number' ? maxNewTokensValue : 4000}
            />
            <InputNumber
              size='small'
              className='w-20'
              min={1}
              max={20480}
              step={1}
              onChange={handleInputChange}
              value={maxNewTokensValue}
            />
          </div>
        )}
      >
        <Tooltip title={t('max_new_tokens')} placement='bottom' arrow={false}>
          <div className='flex w-8 h-8 items-center justify-center rounded-md hover:bg-[rgb(221,221,221,0.6)] cursor-pointer'>
            <ControlOutlined />
          </div>
        </Tooltip>
      </Popover>
      <span className='text-sm ml-2'>{maxNewTokensValue}</span>
    </div>
  );
};

export default memo(MaxNewTokens);
