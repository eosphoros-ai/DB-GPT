import { ControlOutlined } from '@ant-design/icons';
import { InputNumber, Popover, Slider, Tooltip } from 'antd';
import React, { memo } from 'react';
import { useTranslation } from 'react-i18next';

const Temperature: React.FC<{ temperatureValue: any; setTemperatureValue: any }> = ({
  temperatureValue,
  setTemperatureValue,
}) => {
  const { t } = useTranslation();

  // temperature变化;
  const onChange = (value: any) => {
    if (value === null || Number.isNaN(Number(value))) {
      return;
    }
    setTemperatureValue(value);
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
              className='w-20'
              min={0}
              max={1}
              step={0.1}
              onChange={onChange}
              value={typeof temperatureValue === 'number' ? temperatureValue : 0}
            />
            <InputNumber
              size='small'
              className='w-14'
              min={0}
              max={1}
              step={0.1}
              onChange={onChange}
              value={temperatureValue}
            />
          </div>
        )}
      >
        <Tooltip title={t('temperature')} placement='bottom' arrow={false}>
          <div className='flex w-8 h-8 items-center justify-center rounded-md hover:bg-[rgb(221,221,221,0.6)] cursor-pointer'>
            <ControlOutlined />
          </div>
        </Tooltip>
      </Popover>
      <span className='text-sm ml-2'>{temperatureValue}</span>
    </div>
  );
};

export default memo(Temperature);
