import { apiInterceptors, getChunkStrategies, getDocumentList, syncBatchDocument } from '@/client/api';
import { DoneIcon, FileError, PendingIcon, SyncIcon } from '@/components/icons';
import { File, IChunkStrategyResponse, ISyncBatchParameter, StepChangeParams } from '@/types/knowledge';
import Icon from '@ant-design/icons';
import { Alert, Button, Collapse, Form, Spin, message } from 'antd';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import StrategyForm from './strategy-form';

type IProps = {
  spaceName: string;
  docType: string;
  handleStepChange: (params: StepChangeParams) => void;
  uploadFiles: Array<File>;
};

type FieldType = {
  fileStrategies: Array<ISyncBatchParameter>;
};

let intervalId: string | number | NodeJS.Timeout | undefined;

export default function Segmentation(props: IProps) {
  const { spaceName, docType, uploadFiles, handleStepChange } = props;
  const { t } = useTranslation();
  const [form] = Form.useForm();
  const [files, setFiles] = useState(uploadFiles);
  const [loading, setLoading] = useState<boolean>();
  const [strategies, setStrategies] = useState<Array<IChunkStrategyResponse>>([]);
  const [syncStatus, setSyncStatus] = useState<string>('');

  async function getStrategies() {
    setLoading(true);
    const [, allStrategies] = await apiInterceptors(getChunkStrategies());
    setLoading(false);
    setStrategies((allStrategies || [])?.filter(i => i.type.indexOf(docType) > -1));
  }

  useEffect(() => {
    getStrategies();
    return () => {
      intervalId && clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleFinish = async (data: FieldType) => {
    if (checkParameter(data)) {
      setLoading(true);
      const [, result] = await apiInterceptors(syncBatchDocument(spaceName, data.fileStrategies));
      setLoading(false);
      if (result?.tasks && result?.tasks?.length > 0) {
        message.success(`Segemation task start successfully. task id: ${result?.tasks.join(',')}`);
        setSyncStatus('RUNNING');
        const docIds = data.fileStrategies.map(i => i.doc_id);
        intervalId = setInterval(async () => {
          const status = await updateSyncStatus(docIds);
          if (status === 'FINISHED') {
            clearInterval(intervalId);
            setSyncStatus('FINISHED');
            message.success('Congratulation, All files sync successfully.');
            handleStepChange({
              label: 'finish',
            });
          } else if (status === 'FAILED') {
            clearInterval(intervalId);
            handleStepChange({
              label: 'finish',
            });
          }
        }, 3000);
      }
    }
  };

  function checkParameter(data: FieldType) {
    let checked = true;
    if (syncStatus === 'RUNNING') {
      checked = false;
      message.warning('The task is still running, do not submit it again.');
    }
    const { fileStrategies } = data;
    fileStrategies.map(item => {
      const name = item?.chunk_parameters?.chunk_strategy || 'Automatic';
      if (!name) {
        message.error(`Please select chunk strategy for ${item.name}.`);
        checked = false;
      }
      const strategy = strategies.filter(item => item.strategy === name)[0];
      const newParam: any = {
        chunk_strategy: item?.chunk_parameters?.chunk_strategy || 'Automatic',
      };
      if (strategy && strategy.parameters) {
        // remove unused parameter, otherwise api will failed.
        strategy.parameters.forEach(param => {
          const paramName = param.param_name;
          newParam[paramName] = (item?.chunk_parameters as any)[paramName];
        });
      }
      item.chunk_parameters = newParam;
    });
    return checked;
  }

  async function updateSyncStatus(docIds: Array<number>) {
    const [, docs] = await apiInterceptors(
      getDocumentList(spaceName as any, {
        doc_ids: docIds,
      }),
    );
    if (docs?.data && docs?.data.length > 0) {
      const copy = [...files!];
      // set file status one by one
      docs?.data.map(doc => {
        const file = copy?.filter(file => file.doc_id === doc.id)?.[0];
        if (file) {
          file.status = doc.status;
        }
      });
      setFiles(copy);
      // all doc sync finished
      if (docs?.data.every(item => item.status === 'FINISHED' || item.status === 'FAILED')) {
        return 'FINISHED';
      }
    }
  }

  function renderStrategy() {
    if (!strategies || !strategies.length) {
      return <Alert message={`Cannot find one strategy for ${docType} type knowledge.`} type='warning' />;
    }
    return (
      <Form.List name='fileStrategies'>
        {fields => {
          switch (docType) {
            case 'TEXT':
            case 'URL':
            case 'YUQUEURL':
              return fields?.map(field => (
                <StrategyForm
                  key={field.key}
                  strategies={strategies}
                  docType={docType}
                  fileName={files![field.name].name}
                  field={field}
                />
              ));
            case 'DOCUMENT':
              return (
                <Collapse defaultActiveKey={0} size={files.length > 5 ? 'small' : 'middle'}>
                  {fields?.map(field => (
                    // field [{name: 0, key: 0, isListField: true, fieldKey: 0}, {name: 1, key: 1, isListField: true, fieldKey: 1}]
                    <Collapse.Panel
                      header={`${field.name + 1}. ${files![field.name].name}`}
                      key={field.key}
                      extra={renderSyncStatus(field.name)}
                    >
                      <StrategyForm
                        strategies={strategies}
                        docType={docType}
                        fileName={files![field.name].name}
                        field={field}
                      />
                    </Collapse.Panel>
                  ))}
                </Collapse>
              );
          }
        }}
      </Form.List>
    );
  }

  function renderSyncStatus(index: number) {
    const status = files![index].status;
    switch (status) {
      case 'FINISHED':
        return <Icon component={DoneIcon} />;
      case 'RUNNING':
        return <Icon className='animate-spin animate-infinite' component={SyncIcon} />;
      case 'FAILED':
        return <Icon component={FileError} />;
      default:
        return <Icon component={PendingIcon} />;
    }
  }

  return (
    <Spin spinning={loading}>
      <Form
        labelCol={{ span: 6 }}
        wrapperCol={{ span: 18 }}
        labelAlign='right'
        form={form}
        size='large'
        className='mt-4'
        layout='horizontal'
        name='basic'
        autoComplete='off'
        initialValues={{
          fileStrategies: files,
        }}
        onFinish={handleFinish}
      >
        {renderStrategy()}
        <Form.Item className='mt-4'>
          <Button
            onClick={() => {
              handleStepChange({ label: 'back' });
            }}
            className='mr-4'
          >{`${t('Back')}`}</Button>
          <Button type='primary' htmlType='submit' loading={loading || syncStatus === 'RUNNING'}>
            {t('Process')}
          </Button>
        </Form.Item>
      </Form>
    </Spin>
  );
}
