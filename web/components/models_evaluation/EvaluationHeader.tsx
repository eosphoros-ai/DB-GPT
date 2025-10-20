import { TabKey } from '@/types/models_evaluation';
import { ReloadOutlined } from '@ant-design/icons';
import { Button, Segmented, Tooltip } from 'antd';
import { t } from 'i18next';
import { useState } from 'react';
import { NewEvaluationModal } from './NewEvaluationModal';
import { NavTo } from './components/nav-to';
import { useEvaluation } from './context/EvaluationContext';

type Props = {
  activeKey?: TabKey;
  onTabChange?: (v: TabKey) => void;
  filterValue?: string;
  onSearch?: (v: string) => void;
};

export const EvaluationHeader = (props: Props) => {
  const { onTabChange, activeKey = 'all' } = props;
  const { refresh } = useEvaluation();

  const [evaluationVisible, setEvaluationVisible] = useState(false);

  const createEvaluations = () => {
    setEvaluationVisible(true);
  };

  return (
    <div className='flex items-center justify-between'>
      <div className='flex items-center gap-4'>
        <Segmented
          className='backdrop-filter h-10 backdrop-blur-lg bg-white bg-opacity-30 border border-white rounded-lg shadow p-1 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
          options={[
            {
              value: 'all' as const,
              label: t('all_models_evaluation'),
            },
          ]}
          onChange={onTabChange}
          value={activeKey}
        />
        {/* <Input
          variant='filled'
          value={filterValue}
          prefix={<SearchOutlined />}
          placeholder={t('please_enter_the_keywords')}
          onChange={onFilterChange}
          onPressEnter={onFilterChange}
          allowClear
          className='w-[230px] h-[40px] border-1 border-white backdrop-filter backdrop-blur-lg bg-white bg-opacity-30 dark:border-[#6f7f95] dark:bg-[#6f7f95] dark:bg-opacity-60'
        /> */}
      </div>
      <div>
        <Tooltip title={t('refresh_list')}>
          <ReloadOutlined onClick={refresh} className='p-2 cursor-pointer' />
        </Tooltip>
        <NavTo
          href='/models_evaluation/datasets'
          className='border-none text-white bg-button-gradient h-full m-2'
          type='primary'
          openNewTab={true}
        >
          {t('evaluation_dataset_info')}
        </NavTo>
        <Button className='border-none text-white bg-button-gradient h-full' onClick={createEvaluations}>
          {t('create_evaluation')}
        </Button>
        <NewEvaluationModal open={evaluationVisible} onCancel={() => setEvaluationVisible(false)} onOk={refresh} />
      </div>
    </div>
  );
};
