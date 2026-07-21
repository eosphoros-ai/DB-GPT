/* eslint-disable */
import MarkDownContext from '@/new-components/common/MarkdownContext';
import { ExclamationCircleOutlined } from '@ant-design/icons';
import { Modal, Select } from 'antd';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

type PromptSelectType = {
  promptList: Record<string, any>[];
  value?: string;
  onChange?: (value: string) => void;
};
const PromptSelect: React.FC<PromptSelectType> = ({ value, onChange, promptList }) => {
  const { t } = useTranslation();
  const [showPrompt, setShowPrompt] = useState<boolean>(false);
  const [curPrompt, setCurPrompt] = useState<Record<string, any>>();

  useEffect(() => {
    if (value) {
      const filterPrompt = promptList?.filter(item => item.prompt_code === value)[0];
      setCurPrompt(filterPrompt);
    }
  }, [promptList, value]);

  return (
    <div className='w-2/5 flex items-center gap-2'>
      <Select
        className='w-1/2'
        placeholder='select prompt'
        options={promptList}
        fieldNames={{ label: 'prompt_name', value: 'prompt_code' }}
        onChange={value => {
          const filterPrompt = promptList?.filter(item => item.prompt_code === value)[0];
          setCurPrompt(filterPrompt);
          onChange?.(value);
        }}
        value={value}
        allowClear
        showSearch
      />
      {curPrompt && (
        <span className='text-sm text-blue-500 cursor-pointer' onClick={() => setShowPrompt(true)}>
          <ExclamationCircleOutlined className='mr-1' />
          {t('view_details')}
        </span>
      )}
      <Modal title='Prompt' open={showPrompt} footer={false} width={'60%'} onCancel={() => setShowPrompt(false)}>
        <MarkDownContext>{curPrompt?.content}</MarkDownContext>
      </Modal>
    </div>
  );
};

export default PromptSelect;
