import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import * as Icons from '@ant-design/icons';
import { Input } from 'antd';

const getIconComponent = (iconString: string) => {
  const match = iconString.match(/^icon:(\w+)$/);
  if (match) {
    if (!/(Outlined|Filled|TwoTone)$/.test(match[1])) return null;
    const iconName = match[1] as Extract<
      keyof typeof Icons,
      `${string}Outlined` | `${string}Filled` | `${string}TwoTone`
    >;
    const IconComponent = Icons[iconName];
    return IconComponent ? <IconComponent /> : null;
  }
  return null;
};

export const renderInput = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});
  attr.prefix = getIconComponent(data.ui?.attr?.prefix || '');

  return <Input {...attr} className='w-full' placeholder='please input' allowClear />;
};
