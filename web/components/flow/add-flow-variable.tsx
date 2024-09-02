import { apiInterceptors, getFlowNodes } from '@/client/api';
import { IFlowNode } from '@/types/flow';
import { FLOW_NODES_KEY } from '@/utils';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, Modal } from 'antd';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

type GroupType = { category: string; categoryLabel: string; nodes: IFlowNode[] };

const AddFlowVariable: React.FC = () => {
  const { t } = useTranslation();
  const [operators, setOperators] = useState<Array<IFlowNode>>([]);
  const [resources, setResources] = useState<Array<IFlowNode>>([]);
  const [operatorsGroup, setOperatorsGroup] = useState<GroupType[]>([]);
  const [resourcesGroup, setResourcesGroup] = useState<GroupType[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const showModal = () => {
    setIsModalOpen(true);
  };

  useEffect(() => {
    getNodes();
  }, []);

  async function getNodes() {
    const [_, data] = await apiInterceptors(getFlowNodes());
    if (data && data.length > 0) {
      localStorage.setItem(FLOW_NODES_KEY, JSON.stringify(data));
      const operatorNodes = data.filter(node => node.flow_type === 'operator');
      const resourceNodes = data.filter(node => node.flow_type === 'resource');
      setOperators(operatorNodes);
      setResources(resourceNodes);
      setOperatorsGroup(groupNodes(operatorNodes));
      setResourcesGroup(groupNodes(resourceNodes));
    }
  }

  function groupNodes(data: IFlowNode[]) {
    const groups: GroupType[] = [];
    const categoryMap: Record<string, { category: string; categoryLabel: string; nodes: IFlowNode[] }> = {};
    data.forEach(item => {
      const { category, category_label } = item;
      if (!categoryMap[category]) {
        categoryMap[category] = { category, categoryLabel: category_label, nodes: [] };
        groups.push(categoryMap[category]);
      }
      categoryMap[category].nodes.push(item);
    });
    return groups;
  }

  const formItemLayout = {
    labelCol: {
      xs: { span: 24 },
      sm: { span: 4 },
    },
    wrapperCol: {
      xs: { span: 24 },
      sm: { span: 20 },
    },
  };

  const formItemLayoutWithOutLabel = {
    wrapperCol: {
      xs: { span: 24, offset: 0 },
      sm: { span: 20, offset: 2 },
    },
  };

  const onFinish = (values: any) => {
    console.log('Received values of form:', values);
  };

  return (
    <>
      <Button
        type='primary'
        className='flex items-center justify-center rounded-full left-4 top-4'
        style={{ zIndex: 1050 }}
        icon={<PlusOutlined />}
        onClick={showModal}
      />

      <Modal title={t('Add_Global_Variable_of_Flow')} open={isModalOpen} footer={null}>
        <Form name='dynamic_form_item' {...formItemLayoutWithOutLabel} onFinish={onFinish} className='mt-8'>
          <Form.List
            name='names'
            rules={[
              {
                validator: async (_, names) => {
                  if (!names || names.length < 2) {
                    return Promise.reject(new Error('At least 2 passengers'));
                  }
                },
              },
            ]}
          >
            {(fields, { add, remove }, { errors }) => (
              <>
                {fields.map((field, index) => (
                  <Form.Item
                    {...(index === 0 ? formItemLayout : formItemLayoutWithOutLabel)}
                    label={index === 0 ? 'Passengers' : ''}
                    required={false}
                    key={field.key}
                  >
                    <Form.Item
                      {...field}
                      validateTrigger={['onChange', 'onBlur']}
                      rules={[
                        {
                          required: true,
                          whitespace: true,
                          message: "Please input passenger's name or delete this field.",
                        },
                      ]}
                      noStyle
                    >
                      <Input placeholder='passenger name' style={{ width: '60%' }} />
                    </Form.Item>
                    {fields.length > 1 ? (
                      <MinusCircleOutlined className='dynamic-delete-button' onClick={() => remove(field.name)} />
                    ) : null}
                  </Form.Item>
                ))}

                <Form.Item>
                  <Button type='dashed' onClick={() => add()} className='w-full' icon={<PlusOutlined />}>
                    Add field
                  </Button>

                  <Form.ErrorList errors={errors} />
                </Form.Item>
              </>
            )}
          </Form.List>

          <Form.Item wrapperCol={{ offset: 18, span: 8 }}>
            <Button type='primary' htmlType='submit'>
              Submit
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

export default AddFlowVariable;
