import AgentModal from '@/components/app/agent-modal';
import AgentCard from '@/components/app/agent-card';
import AppModal from '@/components/app/app-modal';
import AppCard from '@/components/app/app-card';
import { Button, Tabs, TabsProps } from 'antd';
import React from 'react';

export default function App() {
  const [open, setOpen] = React.useState(false);
  const [activeKey, setActiveKey] = React.useState('app');

  const handleCreate = () => {
    setOpen(true);
  };

  const handleCancel = () => {
    setOpen(false);
  };

  const handleTabChange = (activeKey: string) => {
    setActiveKey(activeKey);
  };

  const renderAgentList = () => {
    return (
      <div className="overflow-auto">
        <Button onClick={handleCreate} type="primary" className="mb-6">
          + create
        </Button>
        <div className="w-full h-full flex flex-wrap">
          {new Array(10).fill('item').map((item, index) => {
            return <AgentCard key={index}></AgentCard>;
          })}
        </div>
      </div>
    );
  };

  const renderAppList = () => {
    return (
      <div>
        <Button onClick={handleCreate} type="primary" className="mb-6">
          + create
        </Button>
        <div className="overflow-auto w-full h-[800px] flex flex-wrap pb-24">
          {new Array(10).fill('item').map((item, index) => {
            return <AppCard />;
          })}
        </div>
      </div>
    );
  };

  const items: TabsProps['items'] = [
    {
      key: 'app',
      label: 'App',
      children: renderAppList(),
    },
    {
      key: 'agent',
      label: 'Agent',
      children: renderAgentList(),
    },
  ];

  return (
    <div className="h-screen w-full p-4 md:p-6 overflow-y-aut">
      <Tabs defaultActiveKey="app" items={items} onChange={handleTabChange} />
      {activeKey === 'app' && <AppModal open={open} handleCancel={handleCancel} />}
      {activeKey === 'agent' && <AgentModal open={open} handleCancel={handleCancel} />}
    </div>
  );
}
