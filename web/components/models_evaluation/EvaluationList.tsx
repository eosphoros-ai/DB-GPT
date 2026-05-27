import i18n from '@/app/i18n';
import { EvaluationItem } from '@/types/models_evaluation';
import { Button, Table, Tag, Tooltip } from 'antd';
import { t } from 'i18next';
import { useRouter } from 'next/router';
import React, { useCallback, useEffect } from 'react';
import { useEvaluation } from './context/EvaluationContext';
import styles from './styles.module.css';
import { useTranslation } from 'react-i18next';
interface EvaluationListProps {
  filterValue?: string;
  type?: string;
}

export const EvaluationList: React.FC<EvaluationListProps> = () => {
  // const { filterValue = '', type = 'all' } = props;
  const { data, loading, getModelsEvaluation } = useEvaluation();

  const router = useRouter();

  useEffect(() => {
    getModelsEvaluation?.(1, 20);
  }, []);

  const goToDetail = useCallback((record: EvaluationItem) => {
    router.push(`/models_evaluation/${record.evaluate_code}`);
  }, []);

  const columns = [
    {
      title: i18n.t('evaluation_scene'),
      dataIndex: 'scene_key',
      key: 'scene_key',
      width: '5%',
    },
    {
      title: i18n.t('task_name'),
      dataIndex: 'scene_value',
      key: 'scene_value',
      width: '12%',
    },
    {
      title: i18n.t('evaluation_env'),
      dataIndex: 'evaluation_env',
      key: 'evaluation_env',
      width: '5%',
      render: (evaluation_env: string) => {
        if (evaluation_env === 'DEV') {
          return <span>{i18n.t('evaluation_env_dev')}</span>;
        } else if (evaluation_env === 'TEST') {
          return <span>{i18n.t('evaluation_env_test')}</span>;
        }
        return <span>{evaluation_env}</span>;
      },
    },
    {
      title: i18n.t('evaluation_dataset_name'),
      dataIndex: 'datasets_name',
      key: 'datasets_name',
      width: '6%',
      render: (datasets_name: string) => (
        <Tooltip title={datasets_name}>
          <p className='truncate'>{datasets_name}</p>
        </Tooltip>
      ),
    },
    {
      title: i18n.t('create_time'),
      dataIndex: 'gmt_create',
      key: 'gmt_create',
      width: '10%',
    },
    {
      title: i18n.t('finish_time'),
      dataIndex: 'gmt_modified',
      key: 'gmt_modified',
      width: '10%',
    },
    {
      title: i18n.t('model_name'),
      dataIndex: 'model_list',
      key: 'model_list',
      width: '10%',
      render: (model_list: string[]) => <span>{model_list.join(',')}</span>,
    },
    {
      title: i18n.t('task_status'),
      dataIndex: 'state',
      key: 'state',
      width: '5%',
      render: (state: string, record: EvaluationItem) => {
        let color = 'default';
        let text = state;

        if (state === 'running') {
          color = 'blue';
          text = {i18n.t('running_2')};
        } else if (state === 'complete') {
          color = 'green';
          text = {i18n.t('Completed')};
        } else if (state === 'failed') {
          color = 'red';
          text = {i18n.t('failed')};
        } else if (state === 'pending') {
          color = 'orange';
          text = {i18n.t('pending')};
        }

        if (record?.state === 'failed') {
          return (
            <Tooltip title={record.log_info}>
              <Tag color={color}>{text}</Tag>
            </Tooltip>
          );
        }

        return <Tag color={color}>{text}</Tag>;
      },
    },
    {
      title: i18n.t('round_time'),
      dataIndex: 'round_time',
      key: 'round_time',
      width: '5%',
    },
    {
      title: i18n.t('operator'),
      width: '6%',
      key: 'action',
      render: (_: any, record: EvaluationItem) => {
        return (
          <Button type='link' disabled={record.state !== 'complete'} onClick={() => goToDetail(record)}>
            {i18n.t('View_details')}
          </Button>
        );
      },
    },
  ];

  return (
    <Table
      tableLayout='fixed'
      className={`w-full ${styles.table}`}
      pagination={{
        total: data?.total_count || 0,
        current: data?.page || 1,
        pageSize: data?.page_size || 20,
        onChange: (page, pageSize) => getModelsEvaluation?.(page, pageSize),
        showSizeChanger: true,
        pageSizeOptions: ['10', '20', '50', '100'],
      }}
      loading={loading}
      columns={columns}
      dataSource={data?.items || []}
      rowKey='evaluate_code'
    />
  );
};
