import { IAgent } from '@/types/app';
import { Input } from 'antd';
import React from 'react';

interface IProps {
  agents?: IAgent[];
}

export default function AgentPanel(props: IProps) {
  return (
    <div>
      {/* 资源 */}
      <div>prompt</div>
      <Input />
      {/* 模版 */}
      <div>LLM 使用策略</div>
      <Input />
      {/* 策略 */}
      <div>可用资源</div>
      <Input />
    </div>
  );
}
