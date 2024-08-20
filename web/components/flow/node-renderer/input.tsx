import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { Input } from 'antd';
import * as Icons from '@ant-design/icons';
import { FC } from 'react';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

const isValidIconComponent = (component: any): component is FC => {
  console.log('222', typeof component);

  return component && typeof component === 'function';
};

const getIconComponent = (iconString: string) => {
  const match = iconString.match(/^icon:(\w+)$/);
  if (match) {
    const iconName = match[1] as keyof typeof Icons;
    const IconComponent = Icons[iconName];
    // @ts-ignore
    return IconComponent ? <IconComponent /> : null;
  }
  return null;
};

export const RenderInput = (params: Props) => {
  const { data, defaultValue, onChange } = params;
  const attr = convertKeysToCamelCase(data.ui?.attr || {});
  attr.prefix = getIconComponent(data.ui?.attr?.prefix || '');

  return (
    <Input
      {...attr}
      className="w-full"
      placeholder="please input"
      defaultValue={defaultValue}
      allowClear
      onChange={(e) => {
        onChange(e.target.value);
      }}
    />
  );
};
