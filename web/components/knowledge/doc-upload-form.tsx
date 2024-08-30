import { addDocument, addYuque, apiInterceptors, uploadDocument } from '@/client/api';
import { StepChangeParams } from '@/types/knowledge';
import { InboxOutlined, MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { Button, Form, Input, Spin, Typography, Upload, message } from 'antd';
import { RcFile, UploadChangeParam } from 'antd/es/upload';
import { default as classNames, default as cls } from 'classnames';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

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
  questions: Record<string, any>[];
  doc_token?: string;
};

const { Dragger } = Upload;
const { TextArea } = Input;

export default function DocUploadForm(props: IProps) {
  const { className, handleStepChange, spaceName, docType } = props;
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [spinning, setSpinning] = useState<boolean>(false);
  const [files, setFiles] = useState<any>([]);

  const upload = async (data: FieldType) => {
    const { docName, textSource, text, webPageUrl, doc_token, questions = [] } = data;
    let docId: any;
    setSpinning(true);
    switch (docType) {
      case 'URL':
        [, docId] = await apiInterceptors(
          addDocument(spaceName as string, {
            doc_name: docName,
            content: webPageUrl,
            doc_type: 'URL',
            questions: questions?.map(item => item.question),
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
            questions: questions.map(item => item.question),
          }),
        );
        break;
      case 'YUQUEURL':
        [, docId] = await apiInterceptors(
          addYuque({
            doc_name: docName,
            space_name: spaceName,
            content: webPageUrl,
            doc_type: 'YUQUEURL',
            doc_token: doc_token || '',
            questions: questions?.map(item => item.question),
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

  const handleFileChange = ({ fileList }: UploadChangeParam) => {
    if (fileList.length === 0) {
      form.setFieldValue('originFileObj', null);
    }
  };

  const renderText = () => {
    return (
      <>
        <Form.Item<FieldType>
          label={`${t('Name')}:`}
          name='docName'
          rules={[{ required: true, message: t('Please_input_the_name') }]}
        >
          <Input className='mb-5 h-12' placeholder={t('Please_input_the_name')} />
        </Form.Item>
        <Form.Item<FieldType>
          label={`${t('Text_Source')}:`}
          name='textSource'
          rules={[{ required: true, message: t('Please_input_the_text_source') }]}
        >
          <Input className='mb-5  h-12' placeholder={t('Please_input_the_text_source')} />
        </Form.Item>
        <Form.Item<FieldType>
          label={`${t('Text')}:`}
          name='text'
          rules={[{ required: true, message: t('Please_input_the_description') }]}
        >
          <TextArea rows={4} />
        </Form.Item>
        <Form.Item<FieldType> label={`${t('Correlation_problem')}:`}>
          <Form.List name='questions'>
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name }) => (
                  <div key={key} className={cls('flex flex-1 items-center gap-8 mb-6')}>
                    <Form.Item label='' name={[name, 'question']} className='grow'>
                      <Input placeholder={t('input_question')} />
                    </Form.Item>
                    <Form.Item>
                      <MinusCircleOutlined
                        onClick={() => {
                          remove(name);
                        }}
                      />
                    </Form.Item>
                  </div>
                ))}
                <Form.Item>
                  <Button
                    type='dashed'
                    onClick={() => {
                      add();
                    }}
                    block
                    icon={<PlusOutlined />}
                  >
                    {t('Add_problem')}
                  </Button>
                </Form.Item>
              </>
            )}
          </Form.List>
        </Form.Item>
      </>
    );
  };

  const renderWebPage = () => {
    return (
      <>
        <Form.Item<FieldType>
          label={`${t('Name')}:`}
          name='docName'
          rules={[{ required: true, message: t('Please_input_the_name') }]}
        >
          <Input className='mb-5 h-12' placeholder={t('Please_input_the_name')} />
        </Form.Item>
        <Form.Item<FieldType>
          label={`${t('Web_Page_URL')}:`}
          name='webPageUrl'
          rules={[{ required: true, message: t('Please_input_the_Web_Page_URL') }]}
        >
          <Input className='mb-5  h-12' placeholder={t('Please_input_the_Web_Page_URL')} />
        </Form.Item>
        <Form.Item<FieldType> label={`${t('Correlation_problem')}:`}>
          <Form.List name='questions'>
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name }) => (
                  <div key={key} className={cls('flex flex-1 items-center gap-8 mb-6')}>
                    <Form.Item label='' name={[name, 'question']} className='grow'>
                      <Input placeholder={t('input_question')} />
                    </Form.Item>
                    <Form.Item>
                      <MinusCircleOutlined
                        onClick={() => {
                          remove(name);
                        }}
                      />
                    </Form.Item>
                  </div>
                ))}
                <Form.Item>
                  <Button
                    type='dashed'
                    onClick={() => {
                      add();
                    }}
                    block
                    icon={<PlusOutlined />}
                  >
                    {t('Add_problem')}
                  </Button>
                </Form.Item>
              </>
            )}
          </Form.List>
        </Form.Item>
      </>
    );
  };

  const renderYuquePage = () => {
    return (
      <>
        <Form.Item<FieldType>
          label={`${t('Name')}:`}
          name='docName'
          rules={[{ required: true, message: t('Please_input_the_name') }]}
        >
          <Input className='mb-5 h-12' placeholder={t('Please_input_the_name')} />
        </Form.Item>
        <Form.Item<FieldType>
          label={t('document_url')}
          name='webPageUrl'
          rules={[{ required: true, message: t('input_document_url') }]}
        >
          <Input className='mb-5  h-12' placeholder={t('input_document_url')} />
        </Form.Item>
        <Form.Item<FieldType>
          label={t('document_token')}
          name='doc_token'
          tooltip={
            <>
              {t('Get_token')}
              <Typography.Link href='https://yuque.antfin-inc.com/lark/openapi/dh8zp4' target='_blank'>
                {t('Reference_link')}
              </Typography.Link>
            </>
          }
        >
          <Input className='mb-5  h-12' placeholder={t('input_document_token')} />
        </Form.Item>
        <Form.Item<FieldType> label={`${t('Correlation_problem')}:`}>
          <Form.List name='questions'>
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name }) => (
                  <div key={key} className={cls('flex flex-1 items-center gap-8 mb-6')}>
                    <Form.Item label='' name={[name, 'question']} className='grow'>
                      <Input placeholder={t('input_question')} />
                    </Form.Item>
                    <Form.Item>
                      <MinusCircleOutlined
                        onClick={() => {
                          remove(name);
                        }}
                      />
                    </Form.Item>
                  </div>
                ))}
                <Form.Item>
                  <Button
                    type='dashed'
                    onClick={() => {
                      add();
                    }}
                    block
                    icon={<PlusOutlined />}
                  >
                    {t('Add_problem')}
                  </Button>
                </Form.Item>
              </>
            )}
          </Form.List>
        </Form.Item>
      </>
    );
  };

  const uploadFile = async (options: any) => {
    const { onSuccess, onError, file } = options;
    const formData = new FormData();
    const filename = file?.name;
    formData.append('doc_name', filename);
    formData.append('doc_file', file);
    formData.append('doc_type', 'DOCUMENT');
    const [, docId] = await apiInterceptors(uploadDocument(spaceName, formData));
    if (Number.isInteger(docId)) {
      onSuccess && onSuccess(docId || 0);
      setFiles((files: any) => {
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

  const renderDocument = () => {
    return (
      <>
        <Form.Item<FieldType> name='originFileObj' rules={[{ required: true, message: t('Please_select_file') }]}>
          <Dragger
            multiple
            onChange={handleFileChange}
            maxCount={100}
            accept='.pdf,.ppt,.pptx,.xls,.xlsx,.doc,.docx,.txt,.md,.zip,.csv'
            customRequest={uploadFile}
          >
            <p className='ant-upload-drag-icon'>
              <InboxOutlined />
            </p>
            <p style={{ color: 'rgb(22, 108, 255)', fontSize: '20px' }}>{t('Select_or_Drop_file')}</p>
            <p className='ant-upload-hint' style={{ color: 'rgb(22, 108, 255)' }}>
              PDF, PowerPoint, Excel, Word, Text, Markdown, Zip1, Csv
            </p>
          </Dragger>
        </Form.Item>
        <Form.Item<FieldType> label='关联问题:'>
          <Form.List name='questions'>
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name }) => (
                  <div key={key} className={cls('flex flex-1 items-center gap-8 mb-6')}>
                    <Form.Item label='' name={[name, 'question']} className='grow'>
                      <Input placeholder='请输入问题' />
                    </Form.Item>
                    <Form.Item>
                      <MinusCircleOutlined
                        onClick={() => {
                          remove(name);
                        }}
                      />
                    </Form.Item>
                  </div>
                ))}
                <Form.Item>
                  <Button
                    type='dashed'
                    onClick={() => {
                      add();
                    }}
                    block
                    icon={<PlusOutlined />}
                  >
                    {t('Add_problem')}
                  </Button>
                </Form.Item>
              </>
            )}
          </Form.List>
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
      case 'YUQUEURL':
        return renderYuquePage();
      default:
        return renderText();
    }
  };

  return (
    <Spin spinning={spinning}>
      <Form
        form={form}
        size='large'
        className={classNames('mt-4', className)}
        layout='vertical'
        name='basic'
        initialValues={{ remember: true }}
        autoComplete='off'
        onFinish={upload}
      >
        {renderFormContainer()}
        <Form.Item>
          <Button
            onClick={() => {
              handleStepChange({ label: 'back' });
            }}
            className='mr-4'
          >{`${t('Back')}`}</Button>
          <Button type='primary' loading={spinning} htmlType='submit'>
            {t('Next')}
          </Button>
        </Form.Item>
      </Form>
    </Spin>
  );
}
