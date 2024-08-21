import React from 'react';
import { TreeSelect } from 'antd';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';

export const renderTreeSelect = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <TreeSelect
      {...attr}
      className="w-full nodrag"
      treeDefaultExpandAll
      treeData={data.options}
    />
  );
};
