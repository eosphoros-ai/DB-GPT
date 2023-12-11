import type { AppProps } from 'next/app';
import React, { useContext, useEffect, useRef } from 'react';
import SideBar from '@/components/layout/side-bar';
import { CssVarsProvider, ThemeProvider, useColorScheme } from '@mui/joy/styles';
import { joyTheme } from '@/defaultTheme';
import TopProgressBar from '@/components/layout/top-progress-bar';
import { useTranslation } from 'react-i18next';
import { ChatContext, ChatContextProvider } from '@/app/chat-context';
import classNames from 'classnames';
import '../styles/globals.css';
import '../nprogress.css';
import '../app/i18n';
import { STORAGE_LANG_KEY, STORAGE_THEME_KEY } from '@/utils';
import { ConfigProvider, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import enUS from 'antd/locale/en_US';

type ThemeMode = ReturnType<typeof useColorScheme>['mode'];

function getDefaultTheme(): ThemeMode {
  const theme = localStorage.getItem(STORAGE_THEME_KEY) as ThemeMode;
  if (theme) return theme;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function CssWrapper({ children }: { children: React.ReactElement }) {
  const { i18n } = useTranslation();
  const { mode, setMode } = useColorScheme();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const themeMode = getDefaultTheme();
    setMode(themeMode!);
  }, []);

  useEffect(() => {
    if (ref?.current && mode) {
      ref?.current?.classList?.add(mode);
      if (mode === 'light') {
        ref?.current?.classList?.remove('dark');
      } else {
        ref?.current?.classList?.remove('light');
      }
    }
  }, [ref, mode]);

  useEffect(() => {
    i18n.changeLanguage && i18n.changeLanguage(window.localStorage.getItem(STORAGE_LANG_KEY) || 'en');
  }, [i18n]);

  return (
    <div ref={ref}>
      <TopProgressBar />
      <ChatContextProvider>{children}</ChatContextProvider>
    </div>
  );
}

function LayoutWrapper({ children }: { children: React.ReactNode }) {
  const { isMenuExpand } = useContext(ChatContext);
  const { mode } = useColorScheme();
  const { i18n } = useTranslation();

  return (
    <ConfigProvider
      locale={i18n.language === 'en' ? enUS : zhCN}
      theme={{
        token: {
          borderRadius: 4,
        },
        algorithm: mode === 'dark' ? theme.darkAlgorithm : undefined,
      }}
    >
      <div className="flex w-screen h-screen overflow-hidden">
        <div className={classNames('transition-[width]', isMenuExpand ? 'w-64' : 'w-20', 'hidden', 'md:block')}>
          <SideBar />
        </div>
        <div className="flex flex-col flex-1 relative overflow-hidden">{children}</div>
      </div>
    </ConfigProvider>
  );
}

function MyApp({ Component, pageProps }: AppProps) {
  return (
    <ThemeProvider theme={joyTheme}>
      <CssVarsProvider theme={joyTheme} defaultMode="light">
        <CssWrapper>
          <LayoutWrapper>
            <Component {...pageProps} />
          </LayoutWrapper>
        </CssWrapper>
      </CssVarsProvider>
    </ThemeProvider>
  );
}

export default MyApp;
