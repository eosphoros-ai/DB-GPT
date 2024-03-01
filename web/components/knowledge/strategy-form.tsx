import { IChunkStrategyResponse } from '@/types/knowledge';
import { Alert, Checkbox, Form, FormListFieldData, Input, InputNumber, Radio, RadioChangeEvent } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
const { TextArea } = Input;

type IProps = {
  strategies: Array<IChunkStrategyResponse>;
  docType: string;
  field: FormListFieldData;
  fileName: string;
};

/**
 * render strategies by doc type and file suffix
 */
export default function StrategyForm({ strategies, docType, fileName, field }: IProps) {
  const [selectedStrategy, setSelectedStrategy] = useState<string>();
  let filleSuffix = '';
  if (docType === 'DOCUMENT') {
    // filter strategy by file suffix
    const arr = fileName.split('.');
    filleSuffix = arr[arr.length - 1];
  }
  const ableStrategies = filleSuffix ? strategies.filter((i) => i.suffix.indexOf(filleSuffix) > -1) : strategies;
  const { t } = useTranslation();
  const DEFAULT_STRATEGY = {
    strategy: 'Automatic',
    name: t('Automatic'),
    desc: t('Automatic_desc'),
  };

  function radioChange(e: RadioChangeEvent) {
    setSelectedStrategy(e.target.value);
  }

  function renderStrategyParamForm() {
    if (!selectedStrategy) {
      return null;
    }
    if (selectedStrategy === DEFAULT_STRATEGY.strategy) {
      return <p className="my-4">{DEFAULT_STRATEGY.desc}</p>;
    }
    const parameters = ableStrategies?.filter((i) => i.strategy === selectedStrategy)[0].parameters;
    if (!parameters || !parameters.length) {
      return <Alert className="my-2" type="warning" message={t('No_parameter')} />;
    }
    return (
      <div className="mt-2">
        {parameters?.map((param) => (
          <Form.Item
            key={`param_${param.param_name}`}
            label={param.param_name}
            name={[field!.name, 'chunk_parameters', param.param_name]}
            rules={[{ required: true, message: t('Please_input_the_name') }]}
            initialValue={param.default_value}
            valuePropName={param.param_type === 'boolean' ? 'checked' : 'value'}
            tooltip={param.description}
          >
            {renderParamByType(param.param_type)}
          </Form.Item>
        ))}
      </div>
    );
  }

  function renderParamByType(type: string) {
    switch (type) {
      case 'int':
        return <InputNumber className="w-full" min={1} />;
      case 'string':
        return <TextArea className="w-full" rows={2} />;
      case 'boolean':
        return <Checkbox />;
    }
  }
  return (
    <>
      <Form.Item name={[field!.name, 'chunk_parameters', 'chunk_strategy']} initialValue={DEFAULT_STRATEGY.strategy}>
        <Radio.Group style={{ marginTop: 16 }} onChange={radioChange}>
          <Radio value={DEFAULT_STRATEGY.strategy}>{DEFAULT_STRATEGY.name}</Radio>
          {ableStrategies.map((strategy) => (
            <Radio key={`strategy_radio_${strategy.strategy}`} value={strategy.strategy}>
              {strategy.name}
            </Radio>
          ))}
        </Radio.Group>
      </Form.Item>
      {renderStrategyParamForm()}
    </>
  );
}
