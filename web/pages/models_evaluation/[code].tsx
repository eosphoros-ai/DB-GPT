import { Card, Typography, Spin, Descriptions, Tag } from "antd";
import React from "react";
import { useRouter } from "next/router";

const { Title } = Typography;

const EvaluationDetail = () => {
  const router = useRouter();
  const { code } = router.query;

  // 模拟数据，实际应该从API获取
  const evaluationData = {
    evaluate_code: code,
    scene_key: "dataset",
    scene_value: "本地测试任务",
    datasets_name: "2025_07_27_public_500_standard_benchmark_question_list_v2_local_test.xlsx",
    state: "running",
    gmt_create: "2025-10-13 16:34:15",
    gmt_modified: "2025-10-13 16:34:15",
    result: "/Users/alanchen/ant/project/DB-GPT/pilot/benchmark_meta_data/result/5e83aee6b440487c88058312290e6a45/20251013_multi_round_benchmark_result.xlsx",
  };

  if (router.isFallback) {
    return (
      <div className="flex justify-center items-center h-full">
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full w-full dark:bg-gradient-dark bg-gradient-light bg-cover bg-center px-6 py-2 pt-12">
      <Card title="模型评估详情" className="w-full">
        <Title level={4}>评估任务详情</Title>
        
        <Descriptions bordered column={1} className="mt-4">
          <Descriptions.Item label="任务ID">{evaluationData.evaluate_code}</Descriptions.Item>
          <Descriptions.Item label="任务名称">{evaluationData.scene_value}</Descriptions.Item>
          <Descriptions.Item label="数据集">{evaluationData.datasets_name}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag 
              color={
                evaluationData.state === "running" 
                  ? "blue" 
                  : evaluationData.state === "completed" 
                  ? "green" 
                  : "default"
              }
            >
              {evaluationData.state === "running" ? "运行中" : "已完成"}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">{evaluationData.gmt_create}</Descriptions.Item>
          <Descriptions.Item label="完成时间">{evaluationData.gmt_modified}</Descriptions.Item>
          <Descriptions.Item label="结果文件路径">{evaluationData.result}</Descriptions.Item>
        </Descriptions>
        
        <div className="mt-6">
          <Title level={5}>评估配置</Title>
          <p>详细配置信息将在后续版本中展示</p>
        </div>
      </Card>
    </div>
  );
};

export default EvaluationDetail;