import React from 'react';
import { TimePicker } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import type { TimePickerProps } from 'antd';

type Props = {
  formValuesChange:any,
  data: IFlowNodeParameter;
};
export const renderTimePicker = (params: Props) => {
  const { data ,formValuesChange} = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});


  const onChangeTime: TimePickerProps['onChange'] = (time, timeString) => {
    formValuesChange({
      time:timeString
    },{force:true})
  };

  return <TimePicker {...attr} onChange={onChangeTime}  className="w-full" placeholder="please select a moment" />;
};
