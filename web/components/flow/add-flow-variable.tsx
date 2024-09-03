// import { IFlowNode } from '@/types/flow';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, Modal, Select, Space } from 'antd';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';

// ype GroupType = { category: string; categoryLabel: string; nodes: IFlowNode[] };
type ValueType = 'str' | 'int' | 'float' | 'bool' | 'ref';

const { Option } = Select;

const DAG_PARAM_KEY = 'dbgpt.core.flow.params';
const DAG_PARAM_SCOPE = 'flow_priv';

const AddFlowVariable: React.FC = () => {
  const { t } = useTranslation();
  // const [operators, setOperators] = useState<Array<IFlowNode>>([]);
  // const [resources, setResources] = useState<Array<IFlowNode>>([]);
  // const [operatorsGroup, setOperatorsGroup] = useState<GroupType[]>([]);
  // const [resourcesGroup, setResourcesGroup] = useState<GroupType[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [form] = Form.useForm(); // const [form] = Form.useForm<IFlowUpdateParam>();

  const showModal = () => {
    setIsModalOpen(true);
  };

  // TODO: get keys
  // useEffect(() => {
  //   getNodes();
  // }, []);

  // async function getNodes() {
  //   const [_, data] = await apiInterceptors(getFlowNodes());
  //   if (data && data.length > 0) {
  //     localStorage.setItem(FLOW_NODES_KEY, JSON.stringify(data));
  //     const operatorNodes = data.filter(node => node.flow_type === 'operator');
  //     const resourceNodes = data.filter(node => node.flow_type === 'resource');
  //     setOperators(operatorNodes);
  //     setResources(resourceNodes);
  //     setOperatorsGroup(groupNodes(operatorNodes));
  //     setResourcesGroup(groupNodes(resourceNodes));
  //   }
  // }

  // function groupNodes(data: IFlowNode[]) {
  //   const groups: GroupType[] = [];
  //   const categoryMap: Record<string, { category: string; categoryLabel: string; nodes: IFlowNode[] }> = {};
  //   data.forEach(item => {
  //     const { category, category_label } = item;
  //     if (!categoryMap[category]) {
  //       categoryMap[category] = { category, categoryLabel: category_label, nodes: [] };
  //       groups.push(categoryMap[category]);
  //     }
  //     categoryMap[category].nodes.push(item);
  //   });
  //   return groups;
  // }

  const onFinish = (values: any) => {
    console.log('Received values of form:', values);
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

  return (
    <>
      <Button
        type='primary'
        className='flex items-center justify-center rounded-full left-4 top-4'
        style={{ zIndex: 1050 }}
        icon={<PlusOutlined />}
        onClick={showModal}
      />

      <Modal
        title={t('Add_Global_Variable_of_Flow')}
        open={isModalOpen}
        footer={null}
        width={1000}
        styles={{
          body: {
            maxHeight: '70vh',
            overflow: 'scroll',
            backgroundColor: 'rgba(0,0,0,0.02)',
            padding: '0 8px',
            borderRadius: 4,
          },
        }}
        onClose={() => setIsModalOpen(false)}
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
                  <Space key={key} style={{ display: 'flex', marginBottom: 8 }} align='baseline'>
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
                      <Input placeholder='Parameter Value' />
                    </Form.Item>

                    <Form.Item {...restField} name={[name, 'description']} label='描述' style={{ width: 170 }}>
                      <Input placeholder='Parameter Description' />
                    </Form.Item>

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

export default AddFlowVariable;
