import React, { useState, useMemo } from 'react';
import { Button, Modal } from 'antd';
import Editor from '@monaco-editor/react';
import { IFlowNodeParameter } from '@/types/flow';
import { convertKeysToCamelCase } from '@/utils/flow';
import { useTranslation } from 'react-i18next';

type Props = {
  data: IFlowNodeParameter;
  defaultValue: any;
  onChange: (value: any) => void;
};

export const RenderCodeEditor = (params: Props) => {
  const { t } = useTranslation();

  const { data, defaultValue, onChange } = params;
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
    <div style={{ textAlign: 'center' }} className="p-2 text-sm">
      <Button type="primary" onClick={showModal}>
        {t('openCodeEditor')}
      </Button>

      <Modal title={t('openCodeEditor')} width={modalWidth} open={isModalOpen} onOk={onOk} onCancel={onCancel}>
        <Editor
          {...attr}
          width={data?.ui?.editor?.width || '100%'}
          value={defaultValue}
          height={data?.ui?.editor?.height || 200}
          defaultLanguage={data?.ui?.language}
          onChange={onChange}
          theme="vs-dark"
          options={{
            minimap: {
              enabled: false,
            },
            wordWrap: 'on',
          }}
        />
      </Modal>
    </div>
  );
};
