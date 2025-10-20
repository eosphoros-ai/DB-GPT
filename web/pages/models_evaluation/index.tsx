import { ConfigProvider } from 'antd';
import { useState } from 'react';

import { EvaluationHeader } from '@/components/models_evaluation/EvaluationHeader';
import { EvaluationList } from '@/components/models_evaluation/EvaluationList';
import { EvaluationProvider } from '@/components/models_evaluation/context/EvaluationContext';
import { TabKey } from '@/types/models_evaluation';
import { useTranslation } from 'react-i18next';

const ModelsEvaluation = () => {
  const [activeKey, setActiveKey] = useState<TabKey>('all');
  const [filterValue, setFilterValue] = useState<string>('');
  const { t: _t } = useTranslation();

  return (
    <ConfigProvider
      theme={{
        components: {
          Segmented: {
            itemSelectedBg: '#2867f5',
            itemSelectedColor: 'white',
          },
        },
      }}
    >
      <EvaluationProvider filterValue={filterValue} type={activeKey}>
        <div className='flex flex-col h-full w-full  dark:bg-gradient-dark bg-gradient-light bg-cover bg-center px-6 py-2 pt-12'>
          <EvaluationHeader
            activeKey={activeKey}
            onTabChange={setActiveKey}
            filterValue={filterValue}
            onSearch={setFilterValue}
          />
          <div className='flex flex-col h-full w-full overflow-y-auto'>
            <EvaluationList filterValue={filterValue} type={activeKey} />
          </div>
        </div>
      </EvaluationProvider>
    </ConfigProvider>
  );
};

export default ModelsEvaluation;
