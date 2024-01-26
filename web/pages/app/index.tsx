import AgentCard from '@/components/app/agent-card';
import { Tabs, TabsProps } from 'antd';
import React from 'react';

export default function App() {
  const renderAgentList = () => {
    return (
      <div className="w-full h-full flex flex-wrap">
        {new Array(10).fill('item').map((item, index) => {
          return <AgentCard key={index}></AgentCard>;
        })}
      </div>
    );
  };

  const items: TabsProps['items'] = [
    {
      key: 'app',
      label: 'App',
      children: <h1>dddd</h1>,
    },
    {
      key: 'agent',
      label: 'Agent',
      children: renderAgentList(),
    },
  ];

  return (
    <div className="h-screen w-full p-4 md:p-6 overflow-y-aut">
      <Tabs defaultActiveKey="agent" items={items} />
    </div>
  );
}
