import { ModelSvg } from '@/components/icons';
import Icon, {
  AppstoreOutlined,
  ConsoleSqlOutlined,
  ForkOutlined,
  MessageOutlined,
  PartitionOutlined,
  TeamOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { STORAGE_USERINFO_KEY } from '@/utils/constants/index';
import { ConfigProvider, Tabs } from 'antd';
import { useRouter } from 'next/router';
import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import './style.css';

function ConstructLayout({ children }: { children: React.ReactNode }) {
  const { t, i18n } = useTranslation();
  const items = useMemo(() => [
    {
      key: 'app',
      name: t('App'),
      path: '/app',
      icon: <AppstoreOutlined />,
      // operations: (
      //   <Button
      //     className='border-none text-white bg-button-gradient h-full flex items-center'
      //     icon={<PlusOutlined className='text-base' />}
      //     // onClick={handleCreate}
      //   >
      //     {t('create_app')}
      //   </Button>
      // ),
    },
    {
      key: 'flow',
      name: t('awel_flow'),
      icon: <ForkOutlined />,
      path: '/flow',
    },
    {
      key: 'models',
      name: t('model_manage'),
      path: '/models',
      icon: <Icon component={ModelSvg} />,
    },
    {
      key: 'database',
      name: t('Database'),
      icon: <ConsoleSqlOutlined />,
      path: '/database',
    },
    {
      key: 'knowledge',
      name: t('Knowledge_Space'),
      icon: <PartitionOutlined />,
      path: '/knowledge',
    },
    // {
    //   key: 'agent',
    //   name: t('Plugins'),
    //   path: '/agent',
    //   icon: <BuildOutlined />,
    // },
    {
      key: 'prompt',
      name: t('Prompt'),
      icon: <MessageOutlined />,
      path: '/prompt',
    },
    {
      key: 'skills',
      name: t('skills') || '技能',
      path: '/skills',
      icon: <ThunderboltOutlined />,
    },
    {
      key: 'user',
      name: t('user_management'),
      path: '/user',
      icon: <TeamOutlined />,
    },
    // 删除dbgpts社区相关功能
    // {
    //   key: 'dbgpts',
    //   name: t('dbgpts_community'),
    //   path: '/dbgpts',
    //   icon: <BuildOutlined />,
    // },
  ], [t, i18n.language]);
  const router = useRouter();
  const activeKey = router.pathname.split('/')[2];
  // const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)').matches; // unused

  const isSuperAdmin = () => {
    try {
      const raw = localStorage.getItem(STORAGE_USERINFO_KEY);
      if (raw) {
        return JSON.parse(raw).role === 'super_admin';
      }
    } catch {
      /* empty */
    }
    return false;
  };

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
          items={items
            .filter(item => item.key !== 'user' || isSuperAdmin())
            .map(items => {
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
          //     {t('create_app')}
          //   </Button>
          // }
        />
      </ConfigProvider>
    </div>
  );
}

export default ConstructLayout;
