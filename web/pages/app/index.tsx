import AgentModal from '@/components/app/agent-modal';
import AgentCard from '@/components/app/agent-card';
import AppModal from '@/components/app/app-modal';
import AppCard from '@/components/app/app-card';
import { Button, Empty, Tabs, TabsProps } from 'antd';
import React, { useEffect, useState } from 'react';
import { apiInterceptors, getAppList } from '@/client/api';
import { IApp } from '@/types/app';

type TabKey = 'agent' | 'app';

export default function App() {
  const [open, setOpen] = React.useState(false);
  const [activeKey, setActiveKey] = useState<TabKey>('app');
  const [apps, setApps] = useState<IApp[]>([]);

  const handleCreate = () => {
    setOpen(true);
  };

  const handleCancel = () => {
    setOpen(false);
  };

  const handleTabChange = (activeKey: string) => {
    setActiveKey(activeKey as TabKey);
  };

  const initData = async () => {
    const [_, data] = await apiInterceptors(getAppList());
    if (!data) return;

    setApps(data || []);
  };

  useEffect(() => {
    initData();
  }, []);

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
        {apps.length > 0 ? (
          <div className="overflow-auto w-full h-[800px] flex flex-wrap pb-24">
            {apps.map((app, index) => {
              return <AppCard key={index} app={app} updateApps={initData} />;
            })}
          </div>
        ) : (
          <Empty />
        )}
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
      {activeKey === 'app' && <AppModal updateApps={initData} open={open} handleCancel={handleCancel} />}
      {activeKey === 'agent' && <AgentModal open={open} handleCancel={handleCancel} />}
    </div>
  );
}
