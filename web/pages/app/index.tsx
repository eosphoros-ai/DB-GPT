import AppModal from '@/components/app/app-modal';
import AppCard from '@/components/app/app-card';
import { Button, Empty, Spin, Tabs, TabsProps } from 'antd';
import React, { useEffect, useState } from 'react';
import { apiInterceptors, getAppList } from '@/client/api';
import { IApp } from '@/types/app';

type TabKey = 'agent' | 'app' | 'collected';

type ModalType = 'edit' | 'add';

export default function App() {
  const [open, setOpen] = useState<boolean>(false);
  const [spinning, setSpinning] = useState<boolean>(false);
  const [activeKey, setActiveKey] = useState<TabKey>('app');
  const [apps, setApps] = useState<IApp[]>([]);
  const [curApp, setCurApp] = useState<any>();
  const [modalType, setModalType] = useState<ModalType>('add');

  const handleCreate = () => {
    setModalType('add');
    setOpen(true);
  };

  const handleCancel = () => {
    setOpen(false);
  };

  const handleEdit = (app: any) => {
    setModalType('edit');
    setCurApp(app);
    setOpen(true);
  };

  const handleTabChange = (activeKey: string) => {
    setActiveKey(activeKey as TabKey);
  };

  const initData = async () => {
    setSpinning(true);
    const [error, data] = await apiInterceptors(getAppList());
    if (error) {
      setSpinning(false);
      return;
    }
    if (!data) return;

    setApps(data || []);
    setSpinning(false);
  };

  useEffect(() => {
    initData();
  }, []);

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
          <div className="overflow-auto w-full h-[800px] flex flex-wrap pb-0 gap-4">
            {apps.map((app, index) => {
              if (data.isCollected) {
                return app.is_collected && <AppCard handleEdit={handleEdit} key={index} app={app} updateApps={initData} />;
              } else {
                return <AppCard key={index} handleEdit={handleEdit} app={app} updateApps={initData} />;
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
      key: 'collected',
      label: 'Collected',
      children: renderAppList({ isCollected: true }),
    },
  ];

  return (
    <Spin spinning={spinning}>
      <div className="h-screen w-full p-4 md:p-6 overflow-y-aut">
        <Tabs defaultActiveKey="app" items={items} onChange={handleTabChange} />
        {activeKey === 'app' && open && (
          <AppModal app={modalType === 'edit' ? curApp : {}} type={modalType} updateApps={initData} open={open} handleCancel={handleCancel} />
        )}
      </div>
    </Spin>
  );
}
