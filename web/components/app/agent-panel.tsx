import { IAgent } from '@/types/app';
import { Input } from 'antd';
import React from 'react';

interface IProps {
  agents?: IAgent[];
}

export default function AgentPanel(props: IProps) {
  return (
    <div>
      <div className="mb-3">prompt</div>
      <Input className="mb-3" />
      <div className="mb-3">LLM 使用策略</div>
      <Input className="mb-3" />
      <div className="mb-3">可用资源</div>
      <Input />
    </div>
  );
}
