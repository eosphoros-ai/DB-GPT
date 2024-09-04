import { addFlow, apiInterceptors, updateFlowById } from '@/client/api';
import { IFlowData, IFlowUpdateParam } from '@/types/flow';
import { mapHumpToUnderline } from '@/utils/flow';
import { Button, Checkbox, Form, Input, Modal, message } from 'antd';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ReactFlowInstance } from 'reactflow';

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
  const { t } = useTranslation();
  const router = useRouter();
  const [form] = Form.useForm<IFlowUpdateParam>();
  const [messageApi, contextHolder] = message.useMessage();

  const [deploy, setDeploy] = useState(false);
  const [id, setId] = useState(router.query.id || '');

  useEffect(() => {
    setId(router.query.id || '');
  }, [router.query.id]);

  function onLabelChange(e: React.ChangeEvent<HTMLInputElement>) {
    const label = e.target.value;
    // replace spaces with underscores, convert uppercase letters to lowercase, remove characters other than digits, letters, _, and -.
    const result = label
      .replace(/\s+/g, '_')
      .replace(/[^a-z0-9_-]/g, '')
      .toLowerCase();
    form.setFieldsValue({ name: result });
  }

  async function onSaveFlow() {
    const { name, label, description = '', editable = false, state = 'deployed' } = form.getFieldsValue();
    const reactFlowObject = mapHumpToUnderline(reactFlow.toObject() as IFlowData);

    if (id) {
      const [, , res] = await apiInterceptors(
        updateFlowById(id.toString(), {
          name,
          label,
          description,
          editable,
          uid: id.toString(),
          flow_data: reactFlowObject,
          state,
          variables: flowInfo?.variables,
        }),
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
          variables: flowInfo?.variables,
        }),
      );

      if (res?.uid) {
        messageApi.success(t('save_flow_success'));
        router.push(`/construct/flow/canvas?id=${res.uid}`, undefined, { shallow: true });
      }
    }
    setIsSaveFlowModalOpen(false);
  }

  return (
    <>
      <Modal
        title={t('flow_modal_title')}
        open={isSaveFlowModalOpen}
        onCancel={() => setIsSaveFlowModalOpen(false)}
        footer={[
          <Button key='cancel' onClick={() => setIsSaveFlowModalOpen(false)}>
            {t('cancel')}
          </Button>,
          <Button key='submit' type='primary' onClick={() => form.submit()}>
            {t('verify')}
          </Button>,
        ]}
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
                  // eslint-disable-next-line no-useless-escape
                  const regex = /^[a-zA-Z0-9_\-]+$/;
                  if (!regex.test(value)) {
                    return Promise.reject('Can only contain numbers, letters, underscores, and dashes');
                  }
                  return Promise.resolve();
                },
              }),
            ]}
          >
            <Input />
          </Form.Item>

          <Form.Item label='Description' initialValue={flowInfo?.description} name='description'>
            <TextArea rows={3} />
          </Form.Item>

          <Form.Item label='Editable' name='editable' initialValue={flowInfo?.editable || true} valuePropName='checked'>
            <Checkbox />
          </Form.Item>

          <Form.Item hidden name='state'>
            <Input />
          </Form.Item>

          <Form.Item label='Deploy'>
            <Checkbox
              defaultChecked={flowInfo?.state === 'deployed' || flowInfo?.state === 'running'}
              checked={deploy}
              onChange={e => {
                const val = e.target.checked;
                form.setFieldValue('state', val ? 'deployed' : 'developing');
                setDeploy(val);
              }}
            />
          </Form.Item>
        </Form>
      </Modal>

      {contextHolder}
    </>
  );
};
