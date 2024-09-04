import { apiInterceptors, getKeys, getVariablesByKey } from '@/client/api';
import { IVariableInfo } from '@/types/flow';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Cascader, Form, Input, Modal, Select, Space } from 'antd';
import { uniqBy } from 'lodash';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

const { Option } = Select;

type ValueType = 'str' | 'int' | 'float' | 'bool' | 'ref';
interface Option {
  value?: string | number | null;
  label: React.ReactNode;
  children?: Option[];
  isLeaf?: boolean;
}

interface VariableDict {
  key: string;
  name?: string;
  scope?: string;
  scope_key?: string;
  sys_code?: string;
  user_name?: string;
}

const DAG_PARAM_KEY = 'dbgpt.core.flow.params';
const DAG_PARAM_SCOPE = 'flow_priv';

function escapeVariable(value: string, enableEscape: boolean): string {
  if (!enableEscape) {
    return value;
  }
  return value.replace(/@/g, '\\@').replace(/#/g, '\\#').replace(/%/g, '\\%').replace(/:/g, '\\:');
}

function buildVariableString(variableDict) {
  const scopeSig = '@';
  const sysCodeSig = '#';
  const userSig = '%';
  const kvSig = ':';
  const enableEscape = true;

  const specialChars = new Set([scopeSig, sysCodeSig, userSig, kvSig]);

  // Replace undefined or null with ""
  const newVariableDict: VariableDict = {
    key: variableDict.key || '',
    name: variableDict.name || '',
    scope: variableDict.scope || '',
    scope_key: variableDict.scope_key || '',
    sys_code: variableDict.sys_code || '',
    user_name: variableDict.user_name || '',
  };

  // Check for special characters in values
  for (const [key, value] of Object.entries(newVariableDict)) {
    if (value && [...specialChars].some(char => value.includes(char))) {
      if (enableEscape) {
        newVariableDict[key as keyof VariableDict] = escapeVariable(value, enableEscape);
      } else {
        throw new Error(
          `${key} contains special characters, error value: ${value}, special characters: ${[...specialChars].join(', ')}`,
        );
      }
    }
  }

  const { key, name, scope, scope_key, sys_code, user_name } = newVariableDict;

  let variableStr = `${key}`;

  if (name) {
    variableStr += `${kvSig}${name}`;
  }

  if (scope) {
    variableStr += `${scopeSig}${scope}`;
    if (scope_key) {
      variableStr += `${kvSig}${scope_key}`;
    }
  }

  if (sys_code) {
    variableStr += `${sysCodeSig}${sys_code}`;
  }

  if (user_name) {
    variableStr += `${userSig}${user_name}`;
  }

  return `\${${variableStr}}`;
}

export const AddFlowVariableModal: React.FC = () => {
  const { t } = useTranslation();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [controlTypes, setControlTypes] = useState<ValueType[]>(['str']);
  const [refVariableOptions, setRefVariableOptions] = useState<Option[]>([]);

  useEffect(() => {
    getKeysData();
  }, []);

  const getKeysData = async () => {
    const [err, res] = await apiInterceptors(getKeys());

    if (err) return;

    const keyOptions = res?.map(({ key, label, scope }: IVariableInfo) => ({
      value: key,
      label,
      scope,
      isLeaf: false,
    }));

    setRefVariableOptions(keyOptions);
  };

  const onFinish = (values: any) => {
    const variables = JSON.stringify(values.parameters);
    localStorage.setItem('variables', variables);
    setIsModalOpen(false);
  };

  function onNameChange(e: React.ChangeEvent<HTMLInputElement>, index: number) {
    const name = e.target.value;

    const result = name
      ?.split('_')
      ?.map(word => word.charAt(0).toUpperCase() + word.slice(1))
      ?.join(' ');

    form.setFields([
      {
        name: ['parameters', index, 'label'],
        value: result,
      },
    ]);

    // change value to ref
    const type = form.getFieldValue(['parameters', index, 'value_type']);

    if (type === 'ref') {
      const parameters = form.getFieldValue('parameters');
      const param = parameters?.[index];

      if (param) {
        const { name = '' } = param;
        param.value = `${DAG_PARAM_KEY}:${name}@scope:${DAG_PARAM_SCOPE}`;

        form.setFieldsValue({
          parameters: [...parameters],
        });
      }
    }
  }

  function onValueTypeChange(type: ValueType, index: number) {
    const newControlTypes = [...controlTypes];
    newControlTypes[index] = type;
    setControlTypes(newControlTypes);
  }

  function loadData(selectedOptions: Option[]) {
    const targetOption = selectedOptions[selectedOptions.length - 1];
    const { value, scope } = targetOption as Option & { scope: string };

    setTimeout(async () => {
      const [err, res] = await apiInterceptors(getVariablesByKey({ key: value as string, scope }));

      if (err) return;
      if (res?.total_count === 0) {
        targetOption.isLeaf = true;
        return;
      }

      const uniqueItems = uniqBy(res?.items, 'name');
      targetOption.children = uniqueItems?.map(item => ({
        value: item?.name,
        label: item.label,
        data: item,
      }));
      setRefVariableOptions([...refVariableOptions]);
    }, 1000);
  }

  function onRefTypeValueChange(value: string[], selectedOptions: Option[], index: number) {
    // 选择两个select后，获取到的value，才能设置引用变量的值
    if (value?.length === 2) {
      const [selectRefKey, selectedRefVariable] = selectedOptions;
      const selectedVariableData = selectRefKey?.children?.find(({ value }) => value === selectedRefVariable?.value);
      const variableStr = buildVariableString(selectedVariableData?.data);

      const parameters = form.getFieldValue('parameters');
      const param = parameters?.[index];
      if (param) {
        param.value = variableStr;
        param.category = selectedVariableData?.data?.category;
        param.value_type = selectedVariableData?.data?.value_type;

        form.setFieldsValue({
          parameters: [...parameters],
        });
      }
    }
  }

  return (
    <>
      <Button
        type='primary'
        className='flex items-center justify-center rounded-full left-4 top-4'
        style={{ zIndex: 1050 }}
        icon={<PlusOutlined />}
        onClick={() => setIsModalOpen(true)}
      />

      <Modal
        title={t('Add_Global_Variable_of_Flow')}
        open={isModalOpen}
        footer={null}
        width={1000}
        onCancel={() => setIsModalOpen(false)}
        styles={{
          body: {
            maxHeight: '70vh',
            overflow: 'scroll',
            backgroundColor: 'rgba(0,0,0,0.02)',
            padding: '0 8px',
            borderRadius: 4,
          },
        }}
      >
        <Form
          name='dynamic_form_nest_item'
          onFinish={onFinish}
          form={form}
          autoComplete='off'
          layout='vertical'
          className='mt-8'
          initialValues={{ parameters: [{}] }}
        >
          <Form.List name='parameters'>
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...restField }, index) => (
                  <Space key={key}>
                    <Form.Item
                      {...restField}
                      name={[name, 'name']}
                      label={`参数 ${index + 1} 名称`}
                      style={{ width: 140 }}
                      rules={[
                        { required: true, message: 'Missing parameter name' },
                        {
                          pattern: /^[a-zA-Z0-9]+(_[a-zA-Z0-9]+)*$/,
                          message: '名称必须是字母、数字或下划线，并使用下划线分隔多个单词',
                        },
                      ]}
                    >
                      <Input placeholder='Parameter Name' onChange={e => onNameChange(e, index)} />
                    </Form.Item>

                    <Form.Item
                      {...restField}
                      name={[name, 'label']}
                      label='标题'
                      style={{ width: 130 }}
                      rules={[{ required: true, message: 'Missing parameter label' }]}
                    >
                      <Input placeholder='Parameter Label' />
                    </Form.Item>

                    <Form.Item
                      {...restField}
                      name={[name, 'value_type']}
                      label='类型'
                      style={{ width: 100 }}
                      rules={[{ required: true, message: 'Missing parameter type' }]}
                    >
                      <Select placeholder='Select' onChange={value => onValueTypeChange(value, index)}>
                        {['str', 'int', 'float', 'bool', 'ref'].map(type => (
                          <Option key={type} value={type}>
                            {type}
                          </Option>
                        ))}
                      </Select>
                    </Form.Item>

                    <Form.Item
                      {...restField}
                      name={[name, 'value']}
                      label='值'
                      style={{ width: 320 }}
                      rules={[{ required: true, message: 'Missing parameter value' }]}
                    >
                      {controlTypes[index] === 'ref' ? (
                        <Cascader
                          placeholder='Select Value'
                          options={refVariableOptions}
                          loadData={loadData}
                          onChange={(value, selectedOptions) => onRefTypeValueChange(value, selectedOptions, index)}
                          // displayRender={displayRender}
                          // dropdownRender={dropdownRender}
                          changeOnSelect
                        />
                      ) : (
                        <Input placeholder='Parameter Value' />
                      )}
                    </Form.Item>

                    <Form.Item {...restField} name={[name, 'description']} label='描述' style={{ width: 170 }}>
                      <Input placeholder='Parameter Description' />
                    </Form.Item>

                    <Form.Item name={[name, 'key']} hidden initialValue='dbgpt.core.flow.params' />
                    <Form.Item name={[name, 'scope']} hidden initialValue='flow_priv' />
                    <Form.Item name={[name, 'category']} hidden initialValue='common' />

                    <MinusCircleOutlined onClick={() => remove(name)} />
                  </Space>
                ))}

                <Form.Item>
                  <Button type='dashed' onClick={() => add()} block icon={<PlusOutlined />}>
                    {t('Add_Parameter')}
                  </Button>
                </Form.Item>
              </>
            )}
          </Form.List>

          <Form.Item wrapperCol={{ offset: 20, span: 4 }}>
            <Space>
              <Button onClick={() => setIsModalOpen(false)}>{t('cancel')}</Button>
              <Button type='primary' htmlType='submit'>
                {t('verify')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};
