import { IFlowNodeParameter } from '@/types/flow';
import { Input } from 'antd';
import { convertKeysToCamelCase } from '@/utils/flow';
import classNames from 'classnames';

const { TextArea } = Input;

type TextAreaProps = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderTextArea = (params: TextAreaProps) => {
  const { data, defaultValue, onChange } = params;

  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  return (
    <div className={classNames({ 'mb-3': attr.showCount === true })}>
      <TextArea {...attr} defaultValue={defaultValue} onChange={onChange} />
    </div>
  );
};
