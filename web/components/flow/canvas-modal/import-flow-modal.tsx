import {
  Modal,
  Form,
  Button,
  message,
  Upload,
  UploadFile,
  UploadProps,
  GetProp,
  Radio,
  Space,
} from 'antd';
import { apiInterceptors, importFlow } from '@/client/api';
import { Node, Edge } from 'reactflow';
import { UploadOutlined } from '@ant-design/icons';
import { useTranslation } from 'react-i18next';
import { useState } from 'react';

type Props = {
  isImportModalOpen: boolean;
  setNodes: React.Dispatch<
    React.SetStateAction<Node<any, string | undefined>[]>
  >;
  setEdges: React.Dispatch<React.SetStateAction<Edge<any>[]>>;
  setIsImportFlowModalOpen: (value: boolean) => void;
};
type FileType = Parameters<GetProp<UploadProps, 'beforeUpload'>>[0];

export const ImportFlowModal: React.FC<Props> = ({
  setNodes,
  setEdges,
  isImportModalOpen,
  setIsImportFlowModalOpen,
}) => {
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  const onFlowImport = async (values: any) => {
    values.file = values.file?.[0];

    const formData: any = new FormData();
    fileList.forEach((file) => {
      formData.append('file', file as FileType);
    });
    const [, , res] = await apiInterceptors(importFlow(formData));

    if (res?.success) {
      messageApi.success(t('Export_Flow_Success'));
    } else if (res?.err_msg) {
      messageApi.error(res?.err_msg);
    }

    setIsImportFlowModalOpen(false);
  };

  return (
    <>
      <Modal
        centered
        title={t('Import_Flow')}
        open={isImportModalOpen}
        onCancel={() => setIsImportFlowModalOpen(false)}
        cancelButtonProps={{ className: 'hidden' }}
        okButtonProps={{ className: 'hidden' }}
      >
        <Form
          form={form}
          className='mt-6'
          labelCol={{ span: 6 }}
          wrapperCol={{ span: 16 }}
          onFinish={onFlowImport}
          initialValues={{
            save_flow: false,
          }}
        >
          <Form.Item
            name='file'
            label={t('Select_File')}
            valuePropName='fileList'
            getValueFromEvent={(e) => (Array.isArray(e) ? e : e && e.fileList)}
            rules={[{ required: true, message: 'Please upload a file' }]}
          >
            <Upload accept='.json,.zip' beforeUpload={() => false} maxCount={1}>
              <Button icon={<UploadOutlined />}> {t('Upload')}</Button>
            </Upload>
          </Form.Item>

          <Form.Item name='save_flow' label={t('Save_After_Import')}>
            <Radio.Group>
              <Radio value={true}>{t('Yes')}</Radio>
              <Radio value={false}>{t('No')}</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item wrapperCol={{ offset: 14, span: 8 }}>
            <Space>
              <Button onClick={() => setIsImportFlowModalOpen(false)}>
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
