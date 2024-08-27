import { IFlowNodeParameter } from '@/types/flow';
import { Input } from 'antd';
import { convertKeysToCamelCase } from '@/utils/flow';
import classNames from 'classnames';

const { TextArea } = Input;

export const renderTextArea = (data: IFlowNodeParameter) => {
  const attr = convertKeysToCamelCase(data.ui?.attr || {});
  return (
      <TextArea className="nowheel mb-3" {...attr} />
  );
};