import { addSpace, apiInterceptors } from '@/client/api';
import { StepChangeParams } from '@/types/knowledge';
import { Button, Form, Input, Spin,Select } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

type FieldType = {
  spaceName: string;
  owner: string;
  description: string;
  storage:string;
};

type IProps = {
  handleStepChange: (params: StepChangeParams) => void;
};

export default function SpaceForm(props: IProps) {
  const { t } = useTranslation();
  const { handleStepChange } = props;
  const [spinning, setSpinning] = useState<boolean>(false);

  const handleFinish = async (fieldsValue: FieldType) => {
    const { spaceName, owner, description,storage } = fieldsValue;
    setSpinning(true);
    let vector_type = storage
    const [_, data, res] = await apiInterceptors(
      addSpace({
        name: spaceName,
        vector_type: vector_type,
        owner,
        desc: description,
      }),
    );
    setSpinning(false);
    res?.success && handleStepChange({ label: 'forward', spaceName });
  };
  return (
    <Spin spinning={spinning}>
      <Form
        size="large"
        className="mt-4"
        layout="vertical"
        name="basic"
        initialValues={{ remember: true }}
        autoComplete="off"
        onFinish={handleFinish}
      >
        <Form.Item<FieldType>
          label={t('Knowledge_Space_Name')}
          name="spaceName"
          rules={[
            { required: true, message: t('Please_input_the_name') },
            () => ({
              validator(_, value) {
                if (/[^\u4e00-\u9fa50-9a-zA-Z_-]/.test(value)) {
                  return Promise.reject(new Error(t('the_name_can_only_contain')));
                }
                return Promise.resolve();
              },
            }),
          ]}
        >
          <Input className="mb-5 h-12" placeholder={t('Please_input_the_name')} />
        </Form.Item>
        <Form.Item<FieldType> label={t('Owner')} name="owner" rules={[{ required: true, message: t('Please_input_the_owner') }]}>
          <Input className="mb-5  h-12" placeholder={t('Please_input_the_owner')} />
        </Form.Item>
        <Form.Item<FieldType> label={t('Storage')} name="storage" rules={[{ required: true, message: t('Please_select_the_storage') }]}>
          <Select className="mb-5 h-12" placeholder={t('Please_select_the_storage')}>
            <Select.Option value="VectorStore">Vector Store</Select.Option>
            <Select.Option value="KnowledgeGraph">Knowledge Graph</Select.Option>
            <Select.Option value="FullText">Full Text</Select.Option>
          </Select>
        </Form.Item>
        <Form.Item<FieldType> label={t('Description')} name="description" rules={[{ required: true, message: t('Please_input_the_description') }]}>
          <Input className="mb-5  h-12" placeholder={t('Please_input_the_description')} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit">
            {t('Next')}
          </Button>
        </Form.Item>
      </Form>
    </Spin>
  );
}
