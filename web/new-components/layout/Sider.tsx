import { ChatContext } from '@/app/chat-context';
import { DarkSvg, SunnySvg } from '@/components/icons';
import UserBar from '@/new-components/layout/UserBar';
import { STORAGE_THEME_KEY } from '@/utils/constants/index';
import Icon, { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { Layout, Popover } from 'antd';
import Image from 'next/image';
import Link from 'next/link';
import React, { ReactNode, useCallback, useContext, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

interface SettingItem {
  key: string;
  name: string;
  icon: ReactNode;
  onClick?: () => void;
  placement?: 'top' | 'topLeft';
}

const Sider: React.FC = () => {
  const { mode, setMode } = useContext(ChatContext);
  const { t } = useTranslation();
  const [collapsed, setCollapsed] = useState<boolean>(false);

  const handleToggleTheme = useCallback(() => {
    const theme = mode === 'light' ? 'dark' : 'light';
    setMode(theme);
    localStorage.setItem(STORAGE_THEME_KEY, theme);
  }, [mode, setMode]);

  const handleToggleMenu = useCallback(() => {
    setCollapsed(!collapsed);
  }, [collapsed]);

  const settings: SettingItem[] = useMemo(() => {
    return [
      {
        key: 'theme',
        name: t('Theme'),
        icon: mode === 'dark' ? <Icon component={DarkSvg} /> : <Icon component={SunnySvg} />,
        onClick: handleToggleTheme,
      },
      {
        key: 'fold',
        name: t(collapsed ? 'Show_Sidebar' : 'Close_Sidebar'),
        icon: collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />,
        onClick: handleToggleMenu,
      },
    ];
  }, [collapsed, handleToggleMenu, handleToggleTheme, mode, t]);

  return (
    <Layout.Sider
      theme={mode}
      width={240}
      collapsedWidth={80}
      collapsible={true}
      collapsed={collapsed}
      trigger={null}
      className='flex flex-1 flex-col h-full justify-between  bg-bar dark:bg-[#232734] px-4 pt-4'
    >
      {collapsed ? (
        <></>
      ) : (
        <>
          <Link href='/' className='flex items-center justify-center p-2 pb-4'>
            <Image src='/logo_zh_latest.png' alt='DB-GPT' width={180} height={40} />
          </Link>
          <div></div>
          <div className='flex flex-col'>
            <UserBar />
            <div className='flex items-start justify-between border-t border-dashed border-gray-200 dark:border-gray-700'>
              {settings.map(item => (
                <Popover key={item.key} content={item.name}>
                  <div
                    className='flex-1 flex items-center justify-center cursor-pointer text-xl'
                    onClick={item.onClick}
                  >
                    {item.icon}
                  </div>
                </Popover>
              ))}
            </div>
          </div>
        </>
      )}
    </Layout.Sider>
  );
};

export default Sider;
