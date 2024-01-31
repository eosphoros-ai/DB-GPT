import AgentModal from '@/components/app/agent-modal';
import AgentCard from '@/components/app/agent-card';
import AppModal from '@/components/app/app-modal';
import AppCard from '@/components/app/app-card';
import { Button, Empty, Spin, Tabs, TabsProps } from 'antd';
import React, { useEffect, useState } from 'react';
import { apiInterceptors, getAppList } from '@/client/api';
import { IApp } from '@/types/app';

type TabKey = 'agent' | 'app' | 'collected';

export default function App() {
  const [open, setOpen] = useState<boolean>(false);
  const [spinning, setSpinning] = useState<boolean>(false);
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
    setSpinning(true);
    const [_, data] = await apiInterceptors(getAppList());
    if (!data) return;

    setApps(data || []);
    setSpinning(false);
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

  const renderAppList = (data: { isCollected: boolean }) => {
    const isNull = data.isCollected ? apps.every((item) => !item.is_collected) : apps.length === 0;

    return (
      <div>
        {!data.isCollected && (
          <Button onClick={handleCreate} type="primary" className="mb-6">
            + create
          </Button>
        )}
        {!isNull ? (
          <div className="overflow-auto w-full h-[800px] flex flex-wrap pb-24">
            {apps.map((app, index) => {
              if (data.isCollected) {
                return app.is_collected && <AppCard key={index} app={app} updateApps={initData} />;
              } else {
                return <AppCard key={index} app={app} updateApps={initData} />;
              }
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
      children: renderAppList({ isCollected: false }),
    },
    {
      key: 'agent',
      label: 'Agent',
      children: renderAgentList(),
    },
    {
      key: 'collected',
      label: 'Collected',
      children: renderAppList({ isCollected: true }),
    },
  ];

  return (
    <Spin spinning={spinning}>
      <div className="h-screen w-full p-4 md:p-6 overflow-y-aut">
        <Tabs defaultActiveKey="app" items={items} onChange={handleTabChange} />
        {activeKey === 'app' && <AppModal updateApps={initData} open={open} handleCancel={handleCancel} />}
        {activeKey === 'agent' && <AgentModal open={open} handleCancel={handleCancel} />}
      </div>
    </Spin>
  );
}
