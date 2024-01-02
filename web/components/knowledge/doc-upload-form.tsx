import { Button, Form, Input, Upload, Spin, message } from 'antd';
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { InboxOutlined } from '@ant-design/icons';
import { apiInterceptors, addDocument, uploadDocument } from '@/client/api';
import { RcFile, UploadChangeParam } from 'antd/es/upload';
import { File, StepChangeParams } from '@/types/knowledge';
import { UploadRequestOption as RcCustomRequestOptions } from 'rc-upload/lib/interface';
import classNames from 'classnames';

type FileParams = {
  file: RcFile;
  fileList: FileList;
};

type IProps = {
  className: string;
  handleStepChange: (params: StepChangeParams) => void;
  spaceName: string;
  docType: string;
};

type FieldType = {
  docName: string;
  textSource: string;
  originFileObj: FileParams;
  text: string;
  webPageUrl: string;
};

const { Dragger } = Upload;
const { TextArea } = Input;

export default function DocUploadForm(props: IProps) {
  const { className, handleStepChange, spaceName, docType } = props;
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [spinning, setSpinning] = useState<boolean>(false);
  const [files, setFiles] = useState<Array<File>>([]);

  const upload = async (data: FieldType) => {
    const { docName, textSource, text, webPageUrl } = data;
    let docId;
    setSpinning(true);
    switch (docType) {
      case 'URL':
        [, docId] = await apiInterceptors(
          addDocument(spaceName as string, {
            doc_name: docName,
            content: webPageUrl,
            doc_type: 'URL',
          }),
        );
        break;
      case 'TEXT':
        [, docId] = await apiInterceptors(
          addDocument(spaceName as string, {
            doc_name: docName,
            source: textSource,
            content: text,
            doc_type: 'TEXT',
          }),
        );
        break;
    }
    setSpinning(false);
    if (docType === 'DOCUMENT' && files.length < 1) {
      return message.error('Upload failed, please re-upload.');
    } else if (docType !== 'DOCUMENT' && !docId) {
      return message.error('Upload failed, please re-upload.');
    }
    handleStepChange({
      label: 'forward',
      files:
        docType === 'DOCUMENT'
          ? files
          : [
              {
                name: docName,
                doc_id: docId || -1,
              },
            ],
    });
  };

  const handleFileChange = ({ file, fileList }: UploadChangeParam) => {
    if (fileList.length === 0) {
      form.setFieldValue('originFileObj', null);
    }
  };

  const uploadFile = async (options: RcCustomRequestOptions) => {
    const { onSuccess, onError, file } = options;
    const formData = new FormData();
    const filename = file?.name;
    formData.append('doc_name', filename);
    formData.append('doc_file', file);
    formData.append('doc_type', 'DOCUMENT');
    const [, docId] = await apiInterceptors(uploadDocument(spaceName, formData));
    if (Number.isInteger(docId)) {
      onSuccess && onSuccess(docId || 0);
      setFiles((files) => {
        files.push({
          name: filename,
          doc_id: docId || -1,
        });
        return files;
      });
    } else {
      onError && onError({ name: '', message: '' });
    }
  };

  const renderText = () => {
    return (
      <>
        <Form.Item<FieldType> label={`${t('Name')}:`} name="docName" rules={[{ required: true, message: t('Please_input_the_name') }]}>
          <Input className="mb-5 h-12" placeholder={t('Please_input_the_name')} />
        </Form.Item>
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
        <Form.Item<FieldType> label={`${t('Name')}:`} name="docName" rules={[{ required: true, message: t('Please_input_the_name') }]}>
          <Input className="mb-5 h-12" placeholder={t('Please_input_the_name')} />
        </Form.Item>
        <Form.Item<FieldType>
          label={`${t('Web_Page_URL')}:`}
          name="webPageUrl"
          rules={[{ required: true, message: t('Please_input_the_Web_Page_URL') }]}
        >
          <Input className="mb-5  h-12" placeholder={t('Please_input_the_Web_Page_URL')} />
        </Form.Item>
      </>
    );
  };

  const renderDocument = () => {
    return (
      <>
        <Form.Item<FieldType> name="originFileObj" rules={[{ required: true, message: t('Please_select_file') }]}>
          <Dragger
            multiple
            onChange={handleFileChange}
            maxCount={10}
            accept=".pdf,.ppt,.pptx,.xls,.xlsx,.doc,.docx,.txt,.md"
            customRequest={uploadFile}
          >
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
      case 'URL':
        return renderWebPage();
      case 'DOCUMENT':
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
        className={classNames('mt-4', className)}
        layout="vertical"
        name="basic"
        initialValues={{ remember: true }}
        autoComplete="off"
        onFinish={upload}
      >
        {renderFormContainer()}
        <Form.Item>
          <Button
            onClick={() => {
              handleStepChange({ label: 'back' });
            }}
            className="mr-4"
          >{`${t('Back')}`}</Button>
          <Button type="primary" loading={spinning} htmlType="submit">
            {t('Next')}
          </Button>
        </Form.Item>
      </Form>
    </Spin>
  );
}
