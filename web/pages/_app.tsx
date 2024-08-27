import { ChatContext, ChatContextProvider } from '@/app/chat-context';
import SideBar from '@/components/layout/side-bar';
import TopProgressBar from '@/components/layout/top-progress-bar';
import {
  STORAGE_LANG_KEY,
  STORAGE_USERINFO_KEY,
  STORAGE_USERINFO_VALID_TIME_KEY,
} from '@/utils/constants/index';
import { App, ConfigProvider, MappingAlgorithm, theme } from 'antd';
import enUS from 'antd/locale/en_US';
import zhCN from 'antd/locale/zh_CN';
import classNames from 'classnames';
import type { AppProps } from 'next/app';
import { useRouter } from 'next/router';
import React, { useContext, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

import FloatHelper from '@/new-components/layout/FloatHelper';
import '../app/i18n';
import '../nprogress.css';
import '../styles/globals.css';
import Head from 'next/head';

const antdDarkTheme: MappingAlgorithm = (seedToken, mapToken) => {
  return {
    ...theme.darkAlgorithm(seedToken, mapToken),
    colorBgBase: '#232734',
    colorBorder: '#828282',
    colorBgContainer: '#232734',
  };
};

function CssWrapper({ children }: { children: React.ReactElement }) {
  const { mode } = useContext(ChatContext);
  const { i18n } = useTranslation();

  useEffect(() => {
    if (mode) {
      document.body?.classList?.add(mode);
      if (mode === 'light') {
        document.body?.classList?.remove('dark');
      } else {
        document.body?.classList?.remove('light');
      }
    }
  }, [mode]);

  useEffect(() => {
    i18n.changeLanguage?.(
      window.localStorage.getItem(STORAGE_LANG_KEY) || 'zh'
    );
  }, [i18n]);

  return (
    <div>
      {/* <TopProgressBar /> */}
      {children}
    </div>
  );
}

function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const { isMenuExpand, mode } = useContext(ChatContext);
  const { i18n } = useTranslation();
  const [isLogin, setIsLogin] = useState(false);

  const router = useRouter();

  // 登录检测
  const handleAuth = async () => {
    setIsLogin(false);
    // 如果已有登录信息，直接展示首页
    // if (localStorage.getItem(STORAGE_USERINFO_KEY)) {
    //   setIsLogin(true);
    //   return;
    // }
    const get_user_url = process.env.GET_USER_URL || '';
    var user_not_login_url = process.env.LOGIN_URL;
    // MOCK User info
    var user = {
      user_channel: `dbgpt`,
      user_no: `001`,
      nick_name: `dbgpt`,
    };
    if (user) {
      localStorage.setItem(STORAGE_USERINFO_KEY, JSON.stringify(user));
      localStorage.setItem(
        STORAGE_USERINFO_VALID_TIME_KEY,
        Date.now().toString()
      );
      setIsLogin(true);
    }
  };

  useEffect(() => {
    handleAuth();
  }, []);

  if (!isLogin) {
    return null;
  }

  const renderContent = () => {
    if (router.pathname.includes('mobile')) {
      return <>{children}</>;
    }
    return (
      <div className='flex w-screen h-screen overflow-hidden'>
        <Head>
          <meta
            name='viewport'
            content='initial-scale=1.0, width=device-width, maximum-scale=1'
          />
        </Head>
        {router.pathname !== '/construct/app/extra' && (
          <div
            className={classNames(
              'transition-[width]',
              isMenuExpand ? 'w-60' : 'w-20',
              'hidden',
              'md:block'
            )}
          >
            <SideBar />
          </div>
        )}
        <div className='flex flex-col flex-1 relative overflow-hidden'>
          {children}
        </div>
        <FloatHelper />
      </div>
    );
  };

  return (
    <ConfigProvider
      locale={i18n.language === 'en' ? enUS : zhCN}
      theme={{
        token: {
          colorPrimary: '#0C75FC',
          borderRadius: 4,
        },
        algorithm: mode === 'dark' ? antdDarkTheme : undefined,
      }}
    >
      <App>{renderContent()}</App>
    </ConfigProvider>
  );
}

function MyApp({ Component, pageProps }: AppProps) {
  return (
    <ChatContextProvider>
      <CssWrapper>
        <LayoutWrapper>
          <Component {...pageProps} />
        </LayoutWrapper>
      </CssWrapper>
    </ChatContextProvider>
  );
}

export default MyApp;
