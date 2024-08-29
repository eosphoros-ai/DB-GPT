/* eslint-disable react-hooks/rules-of-hooks */
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import Editor from '@monaco-editor/react';
import { Button, Form, Modal } from 'antd';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

export const renderCodeEditor = (data: IFlowNodeParameter) => {
  const { t } = useTranslation();
  const attr = convertKeysToCamelCase(data.ui?.attr || {});

  const [isModalOpen, setIsModalOpen] = useState(false);
  const showModal = () => {
    setIsModalOpen(true);
  };

  const onOk = () => {
    setIsModalOpen(false);
  };

  const onCancel = () => {
    setIsModalOpen(false);
  };

  const modalWidth = useMemo(() => {
    if (data?.ui?.editor?.width) {
      return data?.ui?.editor?.width + 100;
    }
    return '80%';
  }, [data?.ui?.editor?.width]);

  return (
    <div className='p-2 text-sm'>
      <Button type='default' onClick={showModal}>
        {t('Open_Code_Editor')}
      </Button>

      <Modal title={t('Code_Editor')} width={modalWidth} open={isModalOpen} onOk={onOk} onCancel={onCancel}>
        <Form.Item name={data?.name}>
          <Editor
            {...attr}
            width={data?.ui?.editor?.width || '100%'}
            height={data?.ui?.editor?.height || 200}
            defaultLanguage={data?.ui?.language}
            theme='vs-dark'
            options={{
              minimap: {
                enabled: false,
              },
              wordWrap: 'on',
            }}
          />
        </Form.Item>
      </Modal>
    </div>
  );
};
