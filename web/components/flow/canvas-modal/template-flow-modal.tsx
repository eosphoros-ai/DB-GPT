import { IFlowData, IFlowUpdateParam } from '@/types/flow';
import { Button, Form, Input, Modal, Space, message } from 'antd';
import { useTranslation } from 'react-i18next';
import { ReactFlowInstance } from 'reactflow';

import { getFlowTemplates } from '@/client/api';

import { useEffect, useState } from 'react';

type Props = {
  reactFlow: ReactFlowInstance<any, any>;
  flowInfo?: IFlowUpdateParam;
  isTemplateFlowModalOpen: boolean;
  setisTemplateFlowModalOpen: (value: boolean) => void;
};

export const TemplateFlowModa: React.FC<Props> = ({
  reactFlow,
  flowInfo,
  isTemplateFlowModalOpen,
  setisTemplateFlowModalOpen,
}) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();
  const [loading, setLoading] = useState(false);
  const [templateList, setTemplateList] = useState([]);

  useEffect(() => {
    getFlowTemplates().then(res => {
      console.log(res);
      
      debugger
    });
  })


  const onFlowExport = async (values: any) => {


    setisTemplateFlowModalOpen(false);
  };

  return (
    <>
      <Modal
        title={t('LeadTemplate')}
        open={isTemplateFlowModalOpen}
        onCancel={() => setisTemplateFlowModalOpen(false)}
        cancelButtonProps={{ className: 'hidden' }}
        okButtonProps={{ className: 'hidden' }}
      >
        <Form
          form={form}
          className='mt-6'
          labelCol={{ span: 6 }}
          wrapperCol={{ span: 16 }}
          onFinish={onFlowExport}
          initialValues={{
            export_type: 'json',
            format: 'file',
            uid: flowInfo?.uid,
          }}
        >
          <Form.Item hidden name='uid'>
            <Input />
          </Form.Item>

          <Form.Item wrapperCol={{ offset: 14, span: 8 }}>
            <Space>
              <Button htmlType='button' onClick={() => setisTemplateFlowModalOpen(false)}>
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
