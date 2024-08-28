import { useState } from 'react';
import { Modal, Form, Input, Button, Space, message, Checkbox } from 'antd';
import { IFlowData, IFlowUpdateParam } from '@/types/flow';
import { apiInterceptors, addFlow, updateFlowById } from '@/client/api';
import { mapHumpToUnderline } from '@/utils/flow';
import { useTranslation } from 'react-i18next';
import { ReactFlowInstance } from 'reactflow';
import { useSearchParams } from 'next/navigation';

const { TextArea } = Input;

type Props = {
  reactFlow: ReactFlowInstance<any, any>;
  flowInfo?: IFlowUpdateParam;
  isSaveFlowModalOpen: boolean;
  setIsSaveFlowModalOpen: (value: boolean) => void;
};

export const SaveFlowModal: React.FC<Props> = ({
  reactFlow,
  isSaveFlowModalOpen,
  flowInfo,
  setIsSaveFlowModalOpen,
}) => {
  const [deploy, setDeploy] = useState(true);
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const id = searchParams?.get('id') || '';
  const [form] = Form.useForm<IFlowUpdateParam>();
  const [messageApi, contextHolder] = message.useMessage();

  function onLabelChange(e: React.ChangeEvent<HTMLInputElement>) {
    const label = e.target.value;
    // replace spaces with underscores, convert uppercase letters to lowercase, remove characters other than digits, letters, _, and -.
    let result = label
      .replace(/\s+/g, '_')
      .replace(/[^a-z0-9_-]/g, '')
      .toLowerCase();
    result = result;
    form.setFieldsValue({ name: result });
  }

  async function onSaveFlow() {
    const {
      name,
      label,
      description = '',
      editable = false,
      state = 'deployed',
    } = form.getFieldsValue();
    console.log(form.getFieldsValue());
    const reactFlowObject = mapHumpToUnderline(
      reactFlow.toObject() as IFlowData
    );

    if (id) {
      const [, , res] = await apiInterceptors(
        updateFlowById(id, {
          name,
          label,
          description,
          editable,
          uid: id,
          flow_data: reactFlowObject,
          state,
        })
      );

      if (res?.success) {
        messageApi.success(t('save_flow_success'));
      } else if (res?.err_msg) {
        messageApi.error(res?.err_msg);
      }
    } else {
      const [_, res] = await apiInterceptors(
        addFlow({
          name,
          label,
          description,
          editable,
          flow_data: reactFlowObject,
          state,
        })
      );
      if (res?.uid) {
        messageApi.success(t('save_flow_success'));
        const history = window.history;
        history.pushState(null, '', `/flow/canvas?id=${res.uid}`);
      }
    }
    setIsSaveFlowModalOpen(false);
  }

  return (
    <>
      <Modal
        centered
        title={t('flow_modal_title')}
        open={isSaveFlowModalOpen}
        onCancel={() => {
          setIsSaveFlowModalOpen(false);
        }}
        cancelButtonProps={{ className: 'hidden' }}
        okButtonProps={{ className: 'hidden' }}
      >
        <Form
          name='flow_form'
          form={form}
          labelCol={{ span: 6 }}
          wrapperCol={{ span: 16 }}
          className='mt-6 max-w-2xl'
          initialValues={{ remember: true }}
          onFinish={onSaveFlow}
          autoComplete='off'
        >
          <Form.Item
            label='Title'
            name='label'
            initialValue={flowInfo?.label}
            rules={[{ required: true, message: 'Please input flow title!' }]}
          >
            <Input onChange={onLabelChange} />
          </Form.Item>

          <Form.Item
            label='Name'
            name='name'
            initialValue={flowInfo?.name}
            rules={[
              { required: true, message: 'Please input flow name!' },
              () => ({
                validator(_, value) {
                  const regex = /^[a-zA-Z0-9_\-]+$/;
                  if (!regex.test(value)) {
                    return Promise.reject(
                      'Can only contain numbers, letters, underscores, and dashes'
                    );
                  }
                  return Promise.resolve();
                },
              }),
            ]}
          >
            <Input />
          </Form.Item>

          <Form.Item
            label='Description'
            initialValue={flowInfo?.description}
            name='description'
          >
            <TextArea rows={3} />
          </Form.Item>

          <Form.Item
            label='Editable'
            name='editable'
            initialValue={flowInfo?.editable}
            valuePropName='checked'
          >
            <Checkbox />
          </Form.Item>

          <Form.Item hidden name='state'>
            <Input />
          </Form.Item>

          <Form.Item label='Deploy'>
            <Checkbox
              defaultChecked={
                flowInfo?.state === 'deployed' || flowInfo?.state === 'running'
              }
              checked={deploy}
              onChange={(e) => {
                const val = e.target.checked;
                form.setFieldValue('state', val ? 'deployed' : 'developing');
                setDeploy(val);
              }}
            />
          </Form.Item>

          <Form.Item wrapperCol={{ offset: 14, span: 8 }}>
            <Space>
              <Button
                htmlType='button'
                onClick={() => {
                  setIsSaveFlowModalOpen(false);
                }}
              >
                {t('cancel')}
              </Button>
              <Button type='primary' htmlType='submit'>
                {t('verify')}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {contextHolder}
    </>
  );
};
