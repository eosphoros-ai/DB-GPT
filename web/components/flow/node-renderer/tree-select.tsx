import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { TreeSelect } from 'antd';

export const renderTreeSelect = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return <TreeSelect {...attr} className='w-full nodrag' treeDefaultExpandAll treeData={data.options} />;
};
