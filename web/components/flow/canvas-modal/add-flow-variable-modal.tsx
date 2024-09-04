import { apiInterceptors, getKeys, getVariablesByKey } from '@/client/api';
import { IFlowUpdateParam, IGetKeysResponseData, IVariableItem } from '@/types/flow';
import { buildVariableString } from '@/utils/flow';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Cascader, Form, Input, InputNumber, Modal, Select, Space } from 'antd';
import { DefaultOptionType } from 'antd/es/cascader';
import { uniqBy } from 'lodash';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

const { Option } = Select;
const VALUE_TYPES = ['str', 'int', 'float', 'bool', 'ref'] as const;

type ValueType = (typeof VALUE_TYPES)[number];
type Props = {
  flowInfo?: IFlowUpdateParam;
  setFlowInfo: React.Dispatch<React.SetStateAction<IFlowUpdateParam | undefined>>;
};

export const AddFlowVariableModal: React.FC<Props> = ({ flowInfo, setFlowInfo }) => {
  const { t } = useTranslation();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm();
  const [controlTypes, setControlTypes] = useState<ValueType[]>(['str']);
  const [refVariableOptions, setRefVariableOptions] = useState<DefaultOptionType[]>([]);

  useEffect(() => {
    getKeysData();
  }, []);

  const getKeysData = async () => {
    const [err, res] = await apiInterceptors(getKeys());

    if (err) return;

    const keyOptions = res?.map(({ key, label, scope }: IGetKeysResponseData) => ({
      value: key,
      label,
      scope,
      isLeaf: false,
    }));

    setRefVariableOptions(keyOptions);
  };

  const onFinish = (values: any) => {
    const newFlowInfo = { ...flowInfo, variables: values?.parameters || [] } as IFlowUpdateParam;
    setFlowInfo(newFlowInfo);
    setIsModalOpen(false);
  };

  const onNameChange = (e: React.ChangeEvent<HTMLInputElement>, index: number) => {
    const name = e.target.value;

    const newValue = name
      ?.split('_')
      ?.map(word => word.charAt(0).toUpperCase() + word.slice(1))
      ?.join(' ');

    form.setFields([
      {
        name: ['parameters', index, 'label'],
        value: newValue,
      },
    ]);
  };

  const onValueTypeChange = (type: ValueType, index: number) => {
    const newControlTypes = [...controlTypes];
    newControlTypes[index] = type;
    setControlTypes(newControlTypes);
  };

  const loadData = (selectedOptions: DefaultOptionType[]) => {
    const targetOption = selectedOptions[selectedOptions.length - 1];
    const { value, scope } = targetOption as DefaultOptionType & { scope: string };

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
        item: item,
      }));
      setRefVariableOptions([...refVariableOptions]);
    }, 1000);
  };

  const onRefTypeValueChange = (
    value: (string | number | null)[],
    selectedOptions: DefaultOptionType[],
    index: number,
  ) => {
    // when select ref variable, must be select two options(key and variable)
    if (value?.length !== 2) return;

    const [selectRefKey, selectedRefVariable] = selectedOptions as DefaultOptionType[];
    const selectedVariable = selectRefKey?.children?.find(
      ({ value }) => value === selectedRefVariable?.value,
    ) as DefaultOptionType & { item: IVariableItem };

    // build variable string by rule
    const variableStr = buildVariableString(selectedVariable?.item);
    const parameters = form.getFieldValue('parameters');
    const param = parameters?.[index];
    if (param) {
      param.value = variableStr;
      param.category = selectedVariable?.item?.category;
      param.value_type = selectedVariable?.item?.value_type;

      form.setFieldsValue({
        parameters: [...parameters],
      });
    }
  };

  // Helper function to render the appropriate control component
  const renderVariableValue = (type: string, index: number) => {
    switch (type) {
      case 'ref':
        return (
          <Cascader
            placeholder='Select Value'
            options={refVariableOptions}
            loadData={loadData}
            onChange={(value, selectedOptions) => onRefTypeValueChange(value, selectedOptions, index)}
            changeOnSelect
          />
        );
      case 'str':
        return <Input placeholder='Parameter Value' />;
      case 'int':
        return (
          <InputNumber
            step={1}
            placeholder='Parameter Value'
            parser={value => value?.replace(/[^\-?\d]/g, '') || 0}
            style={{ width: '100%' }}
          />
        );
      case 'float':
        return <InputNumber placeholder='Parameter Value' style={{ width: '100%' }} />;
      case 'bool':
        return (
          <Select placeholder='Select Value'>
            <Option value={true}>True</Option>
            <Option value={false}>False</Option>
          </Select>
        );
      default:
        return <Input placeholder='Parameter Value' />;
    }
  };

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
        width={1000}
        open={isModalOpen}
        styles={{
          body: {
            minHeight: '40vh',
            maxHeight: '65vh',
            overflow: 'scroll',
            backgroundColor: 'rgba(0,0,0,0.02)',
            padding: '0 8px',
            borderRadius: 4,
          },
        }}
        onCancel={() => setIsModalOpen(false)}
        footer={[
          <Button key='cancel' onClick={() => setIsModalOpen(false)}>
            {t('cancel')}
          </Button>,
          <Button key='submit' type='primary' onClick={() => form.submit()}>
            {t('verify')}
          </Button>,
        ]}
      >
        <Form
          name='dynamic_form_nest_item'
          onFinish={onFinish}
          form={form}
          autoComplete='off'
          layout='vertical'
          className='mt-8'
          initialValues={{ parameters: flowInfo?.variables || [{}] }}
        >
          <Form.List name='parameters'>
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...restField }, index) => (
                  <Space key={key} className='hover:bg-gray-100 pt-2 pl-2'>
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
                        {VALUE_TYPES.map(type => (
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
                      {renderVariableValue(controlTypes[index], index)}
                    </Form.Item>

                    <Form.Item {...restField} name={[name, 'description']} label='描述' style={{ width: 170 }}>
                      <Input placeholder='Parameter Description' />
                    </Form.Item>

                    <MinusCircleOutlined onClick={() => remove(name)} />

                    <Form.Item name={[name, 'key']} hidden initialValue='dbgpt.core.flow.params' />
                    <Form.Item name={[name, 'scope']} hidden initialValue='flow_priv' />
                    <Form.Item name={[name, 'category']} hidden initialValue='common' />
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
        </Form>
      </Modal>
    </>
  );
};
