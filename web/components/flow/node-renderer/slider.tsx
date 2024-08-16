import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Col, InputNumber, Row, Slider, Space } from 'antd';
import type { InputNumberProps } from 'antd';
import React, { useState } from 'react';

type TextAreaProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderSlider = (params: TextAreaProps) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});
  const [inputValue, setInputValue] = useState(defaultValue);

  const onChangeSlider: InputNumberProps['onChange'] = (newValue) => {
    setInputValue(newValue as number);
    onChange(newValue as number);
  };

  return (
    <>
      {data?.ui?.show_input ? (
        <Row>
          <Col span={12}>
            <Slider {...attr} onChange={onChangeSlider} value={typeof inputValue === 'number' ? inputValue : 0} />
          </Col>
          <Col span={4}>
            <InputNumber {...attr} style={{ margin: '0 16px' }} value={inputValue} onChange={onChangeSlider} />
          </Col>
        </Row>
      ) : (
        <Slider {...attr} onChange={onChangeSlider} value={typeof inputValue === 'number' ? inputValue : 0} />
      )}
    </>
  );
};
