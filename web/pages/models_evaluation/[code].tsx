import { apiInterceptors } from '@/client/api';
import { getBenchmarkResultDetail } from '@/client/api/models_evaluation/result';
import { BarChart } from '@/components/models_evaluation/components/bar-chart';
import { NavTo } from '@/components/models_evaluation/components/nav-to';
import { Button, Card, Col, Descriptions, Row, Spin, Statistic, Table, Tabs } from 'antd';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
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

  const { code } = router.query;

  return (
    <div className='flex flex-col h-full w-full dark:bg-gradient-dark bg-gradient-light bg-cover bg-center px-6 py-2 pt-12'>
      <Card
        title={
          <div className='flex justify-between'>
            <div>
              <span>数据集评测详情</span>
              <NavTo href='/models_evaluation'>回到列表</NavTo>
            </div>
            <div>
              <NavTo href='/models_evaluation/datasets' openNewTab={true}>
                查看数据集详情
              </NavTo>
              <Button
                type='link'
                target='_blank'
                rel='noopener noreferrer'
                href={`${process.env.API_BASE_URL}/api/v1/evaluate/benchmark_result_download?evaluate_code=${code}`}
              >
                下载评测结果
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
        setError(err.message || '获取评测结果失败');
        return;
      }

      setResultData(data || null);
    } catch (err) {
      setError('获取评测结果失败');
      console.error('获取评测结果失败:', err);
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
        <div>暂无数据</div>
      </div>
    );
  }

  // 计算总计
  const totalRight = resultData.summaries.reduce((sum, item) => sum + item.right, 0);
  const totalWrong = resultData.summaries.reduce((sum, item) => sum + item.wrong, 0);
  const totalFailed = resultData.summaries.reduce((sum, item) => sum + item.failed, 0);
  const totalException = resultData.summaries.reduce((sum, item) => sum + item.exception, 0);
  const totalQuestions = totalRight + totalWrong + totalFailed + totalException;

  // const overallAccuracy = totalQuestions > 0 ? totalRight / totalQuestions : 0;
  // const overallExecRate = totalQuestions > 0 ? (totalRight + totalWrong) / totalQuestions : 0;

  // 准备图表数据
  const chartData: ChartData[] = resultData.summaries
    .map(item => [
      { name: '可执行率', label: item.llmCode, value: item.execRate },
      { name: '正确率', label: item.llmCode, value: item.accuracy },
    ])
    .flat();

  return (
    <>
      <Descriptions
        bordered
        items={[
          {
            key: '1',
            label: '任务ID',
            children: resultData.evaluate_code,
          },
        ]}
      />
      <div className='mt-6'>
        <Row gutter={16} className='mb-4'>
          <Col span={4}>
            <Statistic title='模型数量' value={resultData.summaries?.length} className='border rounded-lg p-4' />
          </Col>
          <Col span={4}>
            <Statistic title='总题数' value={totalQuestions} className='border rounded-lg p-4' />
          </Col>
          <Col span={4}>
            <Statistic title='正确题数' value={totalRight} className='border rounded-lg p-4' />
          </Col>
          <Col span={4}>
            <Statistic title='错误题数' value={totalWrong} className='border rounded-lg p-4' />
          </Col>
          <Col span={4}>
            <Statistic title='失败题数' value={totalFailed} className='border rounded-lg p-4' />
          </Col>
        </Row>
      </div>

      <ModelsTable data={resultData.summaries ?? []} />

      <Tabs
        items={[
          {
            key: 'overview',
            label: '概览',
            children: <BarChart data={chartData} />,
          },
        ]}
      />
    </>
  );
};

const ModelsTable = ({ data }: { data: BenchmarkSummary[] }) => {
  const columns = [
    {
      title: '轮次',
      dataIndex: 'roundId',
      width: '12.5%',
      key: 'roundId',
    },
    {
      title: '模型',
      dataIndex: 'llmCode',
      width: '12.5%',
      key: 'llmCode',
    },
    {
      title: '题目数',
      width: '12.5%',
      key: 'total',
      render: (record: any) => record.right + record.wrong + record.failed,
    },
    {
      title: '正确题数',
      dataIndex: 'right',
      width: '12.5%',
      key: 'right',
    },
    {
      title: '错误题数',
      dataIndex: 'wrong',
      width: '12.5%',
      key: 'wrong',
    },
    {
      title: '失败题数',
      dataIndex: 'failed',
      width: '12.5%',
      key: 'failed',
    },
    {
      title: '正确率',
      dataIndex: 'accuracy',
      width: '12.5%',
      key: 'accuracy',
      render: (value: number) => {
        return `${(value * 100).toFixed(2)}%`;
      },
    },
    {
      title: '可执行率',
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
