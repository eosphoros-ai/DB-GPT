import type { AppProps } from 'next/app';
import React, { useContext, useEffect, useRef } from 'react';
import SideBar from '@/components/layout/side-bar';
import TopProgressBar from '@/components/layout/top-progress-bar';
import { useTranslation } from 'react-i18next';
import { ChatContext, ChatContextProvider } from '@/app/chat-context';
import classNames from 'classnames';
import '../styles/globals.css';
import '../nprogress.css';
import '../app/i18n';
import { STORAGE_LANG_KEY } from '@/utils';
import { ConfigProvider, MappingAlgorithm, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import enUS from 'antd/locale/en_US';
import { CssVarsProvider, ThemeProvider, useColorScheme } from '@mui/joy';
import { joyTheme } from '@/defaultTheme';

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
  const { setMode: setMuiMode } = useColorScheme();

  useEffect(() => {
    setMuiMode(mode);
  }, [mode]);

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
    i18n.changeLanguage && i18n.changeLanguage(window.localStorage.getItem(STORAGE_LANG_KEY) || 'en');
  }, [i18n]);

  return (
    <div>
      <TopProgressBar />
      {children}
    </div>
  );
}

function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const { isMenuExpand, mode } = useContext(ChatContext);
  const { i18n } = useTranslation();

  return (
    <ConfigProvider
      locale={i18n.language === 'en' ? enUS : zhCN}
      theme={{
        token: {
          colorPrimary: '#0069FE',
          borderRadius: 4,
        },
        algorithm: mode === 'dark' ? antdDarkTheme : undefined,
      }}
    >
      <div className="flex w-screen h-screen overflow-hidden">
        <div className={classNames('transition-[width]', isMenuExpand ? 'w-60' : 'w-20', 'hidden', 'md:block')}>
          <SideBar />
        </div>
        <div className="flex flex-col flex-1 relative overflow-hidden">{children}</div>
      </div>
    </ConfigProvider>
  );
}

function MyApp({ Component, pageProps }: AppProps) {
  return (
    <ChatContextProvider>
      <ThemeProvider theme={joyTheme}>
        <CssVarsProvider theme={joyTheme} defaultMode="light">
          <CssWrapper>
            <LayoutWrapper>
              <Component {...pageProps} />
            </LayoutWrapper>
          </CssWrapper>
        </CssVarsProvider>
      </ThemeProvider>
    </ChatContextProvider>
  );
}

export default MyApp;
