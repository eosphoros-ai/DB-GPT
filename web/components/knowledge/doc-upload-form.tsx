import { Button, Form, Input, Switch, Upload, message, Spin } from 'antd';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { InboxOutlined } from '@ant-design/icons';
import { apiInterceptors, addDocument, uploadDocument, syncDocument } from '@/client/api';
import { RcFile, UploadChangeParam } from 'antd/es/upload';
import { StepChangeParams } from '@/types/knowledge';

type FileParams = {
  file: RcFile;
  fileList: FileList;
};

type IProps = {
  handleStepChange: (params: StepChangeParams) => void;
  spaceName: string;
  docType: string;
};

type FieldType = {
  synchChecked: boolean;
  docName: string;
  textSource: string;
  originFileObj: FileParams;
  text: string;
  webPageUrl: string;
};

const { Dragger } = Upload;
const { TextArea } = Input;

export default function DocUploadForm(props: IProps) {
  const { handleStepChange, spaceName, docType } = props;
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [spinning, setSpinning] = useState<boolean>(false);

  const handleFinish = async (data: FieldType) => {
    const { synchChecked, docName, textSource, originFileObj, text, webPageUrl } = data;
    let res;
    setSpinning(true);
    switch (docType) {
      case 'webPage':
        res = await apiInterceptors(
          addDocument(spaceName as string, {
            doc_name: docName,
            content: webPageUrl,
            doc_type: 'URL',
          }),
        );
        break;
      case 'file':
        const formData = new FormData();
        formData.append('doc_name', docName || originFileObj.file.name);
        formData.append('doc_file', originFileObj.file);
        formData.append('doc_type', 'DOCUMENT');

        res = await apiInterceptors(uploadDocument(spaceName as string, formData));
        break;
      default:
        res = await apiInterceptors(
          addDocument(spaceName as string, {
            doc_name: docName,
            source: textSource,
            content: text,
            doc_type: 'TEXT',
          }),
        );
        break;
    }
    synchChecked && handleSync?.(spaceName as string, res?.[1] as number);
    setSpinning(false);
    handleStepChange({ label: 'finish' });
  };

  const handleSync = async (knowledgeName: string, id: number) => {
    await apiInterceptors(syncDocument(knowledgeName, { doc_ids: [id] }));
  };

  const handleFileChange = ({ file, fileList }: UploadChangeParam) => {
    if (!form.getFieldsValue().docName) {
      form.setFieldValue('docName', file.name);
    }
    if (fileList.length === 0) {
      form.setFieldValue('originFileObj', null);
    }
  };

  const beforeUpload = () => {
    const curFile = form.getFieldsValue().originFileObj;
    if (!curFile) {
      return false;
    }
    message.warning(t('Limit_Upload_File_Count_Tips'));
    return Upload.LIST_IGNORE;
  };

  const renderChooseType = () => {};

  const renderText = () => {
    return (
      <>
        <Form.Item<FieldType>
          label={`${t('Text_Source')}:`}
          name="textSource"
          rules={[{ required: true, message: t('Please_input_the_text_source') }]}
        >
          <Input className="mb-5  h-12" placeholder={t('Please_input_the_text_source')} />
        </Form.Item>

        <Form.Item<FieldType> label={`${t('Text')}:`} name="text" rules={[{ required: true, message: t('Please_input_the_description') }]}>
          <TextArea rows={4} />
        </Form.Item>
      </>
    );
  };

  const renderWebPage = () => {
    return (
      <>
        <Form.Item<FieldType> label={`${t('Web_Page_URL')}:`} name="webPageUrl" rules={[{ required: true, message: t('Please_input_the_owner') }]}>
          <Input className="mb-5  h-12" placeholder={t('Please_input_the_Web_Page_URL')} />
        </Form.Item>
      </>
    );
  };

  const renderDocument = () => {
    return (
      <>
        <Form.Item<FieldType> name="originFileObj" rules={[{ required: true, message: t('Please_input_the_owner') }]}>
          <Dragger onChange={handleFileChange} beforeUpload={beforeUpload} multiple={false} accept=".pdf,.ppt,.pptx,.xls,.xlsx,.doc,.docx,.txt,.md">
            <p className="ant-upload-drag-icon">
              <InboxOutlined />
            </p>
            <p style={{ color: 'rgb(22, 108, 255)', fontSize: '20px' }}>{t('Select_or_Drop_file')}</p>
            <p className="ant-upload-hint" style={{ color: 'rgb(22, 108, 255)' }}>
              PDF, PowerPoint, Excel, Word, Text, Markdown,
            </p>
          </Dragger>
        </Form.Item>
      </>
    );
  };

  const renderFormContainer = () => {
    switch (docType) {
      case 'webPage':
        return renderWebPage();
      case 'file':
        return renderDocument();
      default:
        return renderText();
    }
  };

  return (
    <Spin spinning={spinning}>
      <Form
        form={form}
        size="large"
        className="mt-4"
        layout="vertical"
        name="basic"
        initialValues={{ remember: true }}
        autoComplete="off"
        onFinish={handleFinish}
      >
        <Form.Item<FieldType> label={`${t('Name')}:`} name="docName" rules={[{ required: true, message: t('Please_input_the_name') }]}>
          <Input className="mb-5 h-12" placeholder={t('Please_input_the_name')} />
        </Form.Item>
        {renderFormContainer()}
        <Form.Item<FieldType> label={`${t('Synch')}:`} name="synchChecked" initialValue={true}>
          <Switch className="bg-slate-400" defaultChecked />
        </Form.Item>
        <Form.Item>
          <Button
            onClick={() => {
              handleStepChange({ label: 'back' });
            }}
            className="mr-4"
          >{`${t('Back')}`}</Button>
          <Button type="primary" htmlType="submit">
            {t('Finish')}
          </Button>
        </Form.Item>
      </Form>
    </Spin>
  );
}
