import { Card, Typography } from "antd";
import React from "react";

const { Title, Text } = Typography;

const EvaluationDetail = () => {
  return (
    <div className="flex flex-col h-full w-full dark:bg-gradient-dark bg-gradient-light bg-cover bg-center px-6 py-2 pt-12">
      <Card title="模型评估详情" className="w-full">
        <Title level={4}>详情页面占位</Title>
        <Text>这里是模型评估的详细信息页面</Text>
      </Card>
    </div>
  );
};

export default EvaluationDetail;