import React, { useState } from 'react';
import type { TimePickerProps } from 'antd';
import { TimePicker } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';

type TextAreaProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};
export const RenderTimePicker = (params: TextAreaProps) => {
  const { data, defaultValue, onChange } = params;
  const [value, setValue] = useState(defaultValue);
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  // dayjs.extend(customParseFormat);

  const onChangeTime: TimePickerProps['onChange'] = (time, timeString) => {
    onChange(timeString);
    setValue(time);
  };

  return <TimePicker {...attr} style={{ width: '100%' }} value={value} onChange={onChangeTime} />;
};
