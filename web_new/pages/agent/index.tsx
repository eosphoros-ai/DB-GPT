import MarketPlugins from '@/components/agent/market-plugins';
import MyPlugins from '@/components/agent/my-plugins';
import { Tabs } from 'antd';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

function Agent() {
  const { t } = useTranslation();
  const [activeKey, setActiveKey] = useState('market');

  const items: Required<Parameters<typeof Tabs>[0]['items']> = useMemo(
    () => [
      {
        key: 'market',
        label: t('Market_Plugins'),
        children: <MarketPlugins />,
      },
      {
        key: 'my',
        label: t('My_Plugins'),
        children: activeKey === 'market' ? null : <MyPlugins />,
      },
    ],
    [t, activeKey],
  );

  return (
    <div className="h-screen p-4 md:p-6 overflow-y-auto">
      <Tabs activeKey={activeKey} items={items} onChange={setActiveKey} />
    </div>
  );
}

export default Agent;
