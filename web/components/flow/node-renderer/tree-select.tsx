import React, { useState } from 'react';
import { TreeSelect } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};
export const RenderTreeSelect = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <TreeSelect
      {...attr}
      className="w-full nodrag"
      fieldNames={{ label: 'label', value: 'value', children: 'children' }}
      value={defaultValue}
      treeDefaultExpandAll
      onChange={onChange}
      treeData={data.options}
    />
  );
};
