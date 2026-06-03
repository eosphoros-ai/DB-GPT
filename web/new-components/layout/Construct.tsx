import i18n from '@/app/i18n';
import { ModelSvg } from '@/components/icons';
import { useTranslation } from 'react-i18next';
import Icon, {
  AppstoreOutlined,
  BuildOutlined,
  ConsoleSqlOutlined,
  ForkOutlined,
  MessageOutlined,
  PartitionOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { ConfigProvider, Tabs } from 'antd';
import { t } from 'i18next';
import { useRouter } from 'next/router';
import React from 'react';
import './style.css';

function ConstructLayout({ children }: { children: React.ReactNode }) {
  const items = [
    {
      key: 'app',
      name: i18n.t('App'),
      path: '/app',
      icon: <AppstoreOutlined />,
      // operations: (
      //   <Button
      //     className='border-none text-white bg-button-gradient h-full flex items-center'
      //     icon={<PlusOutlined className='text-base' />}
      //     // onClick={handleCreate}
      //   >
      //     {i18n.t('create_app')}
      //   </Button>
      // ),
    },
    {
      key: 'flow',
      name: i18n.t('awel_flow'),
      icon: <ForkOutlined />,
      path: '/flow',
    },
    {
      key: 'models',
      name: i18n.t('model_manage'),
      path: '/models',
      icon: <Icon component={ModelSvg} />,
    },
    {
      key: 'database',
      name: i18n.t('Database'),
      icon: <ConsoleSqlOutlined />,
      path: '/database',
    },
    {
      key: 'knowledge',
      name: i18n.t('Knowledge_Space'),
      icon: <PartitionOutlined />,
      path: '/knowledge',
    },
    // {
    //   key: 'agent',
    //   name: i18n.t('Plugins'),
    //   path: '/agent',
    //   icon: <BuildOutlined />,
    // },
    {
      key: 'prompt',
      name: i18n.t('Prompt'),
      icon: <MessageOutlined />,
      path: '/prompt',
    },
    {
      key: 'skills',
      name: i18n.t('skills') || i18n.t('skill_label'),
      path: '/skills',
      icon: <ThunderboltOutlined />,
    },
    {
      key: 'dbgpts',
      name: i18n.t('dbgpts_community'),
      path: '/dbgpts',
      icon: <BuildOutlined />,
    },
  ];
  const router = useRouter();
  const activeKey = router.pathname.split('/')[2];
  // const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches; // unused

  return (
    <div className='flex flex-col h-full w-full  dark:bg-gradient-dark bg-gradient-light bg-cover bg-center'>
      <ConfigProvider
        theme={{
          components: {
            Button: {
              // defaultBorderColor: 'white',
            },
            Segmented: {
              itemSelectedBg: '#2867f5',
              itemSelectedColor: 'white',
            },
          },
        }}
      >
        <Tabs
          // tabBarStyle={{
          //   background: '#edf8fb',
          //   border: 'none',
          //   height: '3.5rem',
          //   padding: '0 1.5rem',
          //   color: !isDarkMode ? 'white' : 'black',
          // }}
          activeKey={activeKey}
          items={items.map(items => {
            return {
              key: items.key,
              label: items.name,
              children: children,
              icon: items.icon,
            };
          })}
          onTabClick={key => {
            router.push(`/construct/${key}`);
          }}
          // tabBarExtraContent={
          //   <Button
          //     className='border-none text-white bg-button-gradient h-full flex items-center'
          //     icon={<PlusOutlined className='text-base' />}
          //     // onClick={handleCreate}
          //   >
          //     {i18n.t('create_app')}
          //   </Button>
          // }
        />
      </ConfigProvider>
    </div>
  );
}

export default ConstructLayout;
