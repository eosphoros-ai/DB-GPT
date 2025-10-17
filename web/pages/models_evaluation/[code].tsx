import { Card, Typography, Spin, Descriptions, Row, Col, Statistic, Button, Tabs } from "antd";
import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/router";
import { apiInterceptors } from "@/client/api";
import { getBenchmarkResultDetail } from "@/client/api/models_evaluation/result";
import { BarChart } from "./components/bar-chart";
import Link from "next/link";
import styles from "./styles.module.css";
import { Layout } from "./Layout";
import { useEvaluationItem } from "./context/EvaluationContext";

const { Title } = Typography;

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

  const { setData: setActivedEvaluationItem } = useEvaluationItem();

  const goToList = useCallback(() => {
    setActivedEvaluationItem({
      name: '',
      id: '',
      createTime: '',
      modifiedTime: '',
    });
    router.push('/models_evaluation');
  }, []);

  return (
    <div className="flex flex-col h-full w-full dark:bg-gradient-dark bg-gradient-light bg-cover bg-center px-6 py-2 pt-12">
      <Card
        title={
          <>
            <span>模型评估详情</span>
            <Button type="link" onClick={() => goToList()}>
              回到列表
            </Button>
          </>
        }
        className={`w-full h-full flex flex-col ${styles['models-evaluation-detail']}`}
      >
        <EvaluationDetailContent />
      </Card>
    </div>
  )
}

const EvaluationDetailContent = () => {

  const router = useRouter();
  const { code } = router.query;
  const [loading, setLoading] = useState(true);
  const [resultData, setResultData] = useState<BenchmarkResultData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: activedEvaluationItem } = useEvaluationItem();

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
      <div className="flex justify-center items-center h-full">
        <Spin size="large" />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-full">
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex justify-center items-center h-full">
        <div className="text-red-500">{error}</div>
      </div>
    );
  }

  if (!resultData) {
    return (
      <div className="flex justify-center items-center h-full">
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
  const chartData: ChartData[] = resultData.summaries.map(item => [
    { name: '可执行率', label: item.llmCode, value: item.execRate },
    { name: '正确率', label: item.llmCode, value: item.accuracy }
  ]).flat();

  return (
    <>
      <Descriptions
        bordered
        items={[{
          key: '1',
          label: '任务名称',
          children: activedEvaluationItem?.name
        }, {
          key: '2',
          label: '任务ID',
          children: resultData.evaluate_code
        }]}
      />
      <div className="mt-6">
        <Row gutter={16} className="mb-4">
          <Col span={4}>
            <Statistic
              title="模型数"
              value={resultData.summaries?.length}
              className="border rounded-lg p-4"
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="总题数"
              value={totalQuestions}
              className="border rounded-lg p-4"
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="正确题数"
              value={totalRight}
              className="border rounded-lg p-4"
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="错误题数"
              value={totalWrong}
              className="border rounded-lg p-4"
            />
          </Col>
          <Col span={4}>
            <Statistic
              title="失败题数"
              value={totalFailed}
              className="border rounded-lg p-4"
            />
          </Col>
        </Row>
      </div>

      <Tabs
        items={[
          {
            key: 'overview',
            label: '概览',
            children: <BarChart data={chartData} height={400} />
          }
        ]}
      />
      <Button></Button>

    </>
  )
};

const EvaluationDetailWrapper = () => {
  return (
    <Layout>
      <EvaluationDetail />
    </Layout>
  )
}

export default EvaluationDetailWrapper;