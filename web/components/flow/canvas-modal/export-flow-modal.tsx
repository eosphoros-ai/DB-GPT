import { Modal, Form, Input, Button, Space, Radio, message } from 'antd';
import { IFlowData, IFlowUpdateParam } from '@/types/flow';
import { apiInterceptors, exportFlow } from '@/client/api';
import { ReactFlowInstance } from 'reactflow';
import { useTranslation } from 'react-i18next';

type Props = {
  reactFlow: ReactFlowInstance<any, any>;
  flowInfo?: IFlowUpdateParam;
  isExportFlowModalOpen: boolean;
  setIsExportFlowModalOpen: (value: boolean) => void;
};

export const ExportFlowModal: React.FC<Props> = ({
  reactFlow,
  flowInfo,
  isExportFlowModalOpen,
  setIsExportFlowModalOpen,
}) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();

  const onFlowExport = async (values: any) => {
    const flowData = reactFlow.toObject() as IFlowData;
    const blob = new Blob([JSON.stringify(flowData)], {
      type: 'text/plain;charset=utf-8',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = values.file_name || 'flow.json';
    a.click();

    const [, , res] = await apiInterceptors(exportFlow(values), '*');

    if (res?.success) {
      messageApi.success(t('Export_Flow_Success'));
    } else if (res?.err_msg) {
      messageApi.error(res?.err_msg);
    }

    setIsExportFlowModalOpen(false);
  };

  return (
    <>
      <Modal
        centered
        title={t('Export_Flow')}
        open={isExportFlowModalOpen}
        onCancel={() => setIsExportFlowModalOpen(false)}
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
          <Form.Item label={t('Export_File_Type')} name='export_type'>
            <Radio.Group>
              <Radio value='json'>JSON</Radio>
              <Radio value='dbgpts'>DBGPTS</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item label={t('Export_File_Format')} name='format'>
            <Radio.Group>
              <Radio value='file'>File</Radio>
              <Radio value='json'>JSON</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item hidden name='uid'>
            <Input />
          </Form.Item>

          <Form.Item wrapperCol={{ offset: 14, span: 8 }}>
            <Space>
              <Button
                htmlType='button'
                onClick={() => setIsExportFlowModalOpen(false)}
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