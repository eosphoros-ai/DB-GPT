import { ConfigProvider } from 'antd';
import { useState } from 'react';

import { TabKey } from '@/types/models_evaluation';
import { EvaluationHeader } from './EvaluationHeader';
import { EvaluationList } from './EvaluationList';
import { EvaluationProvider } from './context/EvaluationContext';

const ModelsEvaluation = () => {
  const [activeKey, setActiveKey] = useState<TabKey>('all');
  const [filterValue, setFilterValue] = useState<string>('');

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
