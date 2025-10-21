import { apiInterceptors } from '@/client/api';
import { getBenchmarkResultDetail } from '@/client/api/models_evaluation/result';
import { BarChart } from '@/components/models_evaluation/components/bar-chart';
import { NavTo } from '@/components/models_evaluation/components/nav-to';
import { Button, Card, Col, Descriptions, Row, Spin, Statistic, Table, Tabs } from 'antd';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import styles from './styles.module.css';

// 定义数据类型
interface BenchmarkSummary {
  roundId: number;
  llmCode: string;
  right: number;
  wrong: number;
  failed: number;
  exception: number;
  accuracy: number;
  execRate: number;
  outputPath: string;
}

interface BenchmarkResultData {
  evaluate_code: string;
  scene_value: string;
  summaries: BenchmarkSummary[];
}

// 图表数据类型
interface ChartData {
  name: string;
  label: string;
  value: number;
}

const EvaluationDetail = () => {
  const router = useRouter();
  const { t } = useTranslation();

  const { code } = router.query;

  return (
    <div className='flex flex-col h-full w-full dark:bg-gradient-dark bg-gradient-light bg-cover bg-center px-6 py-2 pt-12'>
      <Card
        title={
          <div className='flex justify-between'>
            <div>
              <span>{t('dataset_evaluation_detail')}</span>
              <NavTo href='/models_evaluation'>{t('back_to_list')}</NavTo>
            </div>
            <div>
              <NavTo href='/models_evaluation/datasets' openNewTab={true}>
                {t('evaluation_dataset_info')}
              </NavTo>
              <Button
                type='link'
                target='_blank'
                rel='noopener noreferrer'
                href={`${process.env.API_BASE_URL ?? ''}/api/v1/evaluate/benchmark_result_download?evaluate_code=${code}`}
              >
                {t('download_evaluation_result')}
              </Button>
            </div>
          </div>
        }
        className={`w-full h-full flex flex-col ${styles['models-evaluation-detail']}`}
      >
        <EvaluationDetailContent />
      </Card>
    </div>
  );
};

const EvaluationDetailContent = () => {
  const router = useRouter();
  const { code } = router.query;
  const [loading, setLoading] = useState(true);
  const [resultData, setResultData] = useState<BenchmarkResultData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { t } = useTranslation();

  useEffect(() => {
    if (code) {
      fetchBenchmarkResult(code as string);
    }
  }, [code]);

  const fetchBenchmarkResult = async (evaluateCode: string) => {
    try {
      setLoading(true);
      const [err, data] = await apiInterceptors(getBenchmarkResultDetail(evaluateCode));

      if (err) {
        setError(err.message || t('get_evaluation_result_failed'));
        return;
      }

      setResultData(data || null);
    } catch (err) {
      setError(t('get_evaluation_result_failed'));
      console.error(t('get_evaluation_result_failed'), err);
    } finally {
      setLoading(false);
    }
  };

  if (router.isFallback) {
    return (
      <div className='flex justify-center items-center h-full'>
        <Spin size='large' />
      </div>
    );
  }

  if (loading) {
    return (
      <div className='flex justify-center items-center h-full'>
        <Spin size='large' />
      </div>
    );
  }

  if (error) {
    return (
      <div className='flex justify-center items-center h-full'>
        <div className='text-red-500'>{error}</div>
      </div>
    );
  }

  if (!resultData) {
    return (
      <div className='flex justify-center items-center h-full'>
        <div>{t('no_data')}</div>
      </div>
    );
  }

  // 计算总计
  const totalRight = resultData.summaries.reduce((sum, item) => sum + item.right, 0);
  const totalWrong = resultData.summaries.reduce((sum, item) => sum + item.wrong, 0);
  const totalFailed = resultData.summaries.reduce((sum, item) => sum + item.failed, 0);
  const totalException = resultData.summaries.reduce((sum, item) => sum + item.exception, 0);
  const totalQuestions = totalRight + totalWrong + totalFailed + totalException;

  // 准备图表数据
  const chartData: ChartData[] = resultData.summaries
    .map(item => [
      { name: t('executable_rate'), label: item.llmCode, value: item.execRate },
      { name: t('accuracy'), label: item.llmCode, value: item.accuracy },
    ])
    .flat();

  return (
    <>
      <Descriptions
        bordered
        items={[
          {
            key: '1',
            label: t('task_name'),
            children: resultData.scene_value,
          },
        ]}
      />
      <div className='mt-6'>
        <Row gutter={16} className='mb-4'>
          <Col span={4}>
            <Statistic
              title={t('model_count')}
              value={resultData.summaries?.length}
              className='border rounded-lg p-4'
            />
          </Col>
          <Col span={4}>
            <Statistic title={t('total_questions')} value={totalQuestions} className='border rounded-lg p-4' />
          </Col>
          <Col span={4}>
            <Statistic title={t('correct_questions')} value={totalRight} className='border rounded-lg p-4' />
          </Col>
          <Col span={4}>
            <Statistic title={t('wrong_questions')} value={totalWrong} className='border rounded-lg p-4' />
          </Col>
          <Col span={4}>
            <Statistic title={t('failed_questions')} value={totalFailed} className='border rounded-lg p-4' />
          </Col>
        </Row>
      </div>

      <ModelsTable data={resultData.summaries ?? []} />

      <Tabs
        items={[
          {
            key: 'overview',
            label: t('overview'),
            children: <BarChart data={chartData} />,
          },
        ]}
      />
    </>
  );
};

const ModelsTable = ({ data }: { data: BenchmarkSummary[] }) => {
  const { t } = useTranslation();

  const columns = [
    {
      title: t('round'),
      dataIndex: 'roundId',
      width: '12.5%',
      key: 'roundId',
    },
    {
      title: t('model'),
      dataIndex: 'llmCode',
      width: '12.5%',
      key: 'llmCode',
    },
    {
      title: t('question_count'),
      width: '12.5%',
      key: 'total',
      render: (record: any) => record.right + record.wrong + record.failed,
    },
    {
      title: t('correct_questions'),
      dataIndex: 'right',
      width: '12.5%',
      key: 'right',
    },
    {
      title: t('wrong_questions'),
      dataIndex: 'wrong',
      width: '12.5%',
      key: 'wrong',
    },
    {
      title: t('failed_questions'),
      dataIndex: 'failed',
      width: '12.5%',
      key: 'failed',
    },
    {
      title: t('accuracy'),
      dataIndex: 'accuracy',
      width: '12.5%',
      key: 'accuracy',
      render: (value: number) => {
        return `${(value * 100).toFixed(2)}%`;
      },
    },
    {
      title: t('executable_rate'),
      dataIndex: 'execRate',
      width: '12.5%',
      key: 'execRate',
      render: (value: number) => {
        return `${(value * 100).toFixed(2)}%`;
      },
    },
  ];

  return (
    <Table
      tableLayout='fixed'
      pagination={false}
      className={`w-full ${styles.table}`}
      columns={columns}
      dataSource={data}
    />
  );
};

export default EvaluationDetail;
