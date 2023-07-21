"use client"
import './globals.css'
import '@/nprogress.css';
import React from 'react';
import LeftSider from '@/components/leftSider';
import { CssVarsProvider, ThemeProvider } from '@mui/joy/styles';
import { useColorScheme } from '@/lib/mui';
import { joyTheme } from '@/defaultTheme';
import TopProgressBar from '@/components/topProgressBar';
import DialogueContext from './context/dialogue';
import { useEffect } from 'react';

function CssWrapper({
  children
}: {
  children: React.ReactNode
}) {
  const { mode } = useColorScheme();
  const ref = React.useRef<HTMLDivElement>(null);

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

  return (
    <div ref={ref} className='h-full'>
      <TopProgressBar />
      <DialogueContext>
        <div className={`contents h-full`}>
          <div className="grid h-full w-screen grid-cols-1 grid-rows-[auto,1fr] overflow-hidden text-smd dark:text-gray-300 md:grid-cols-[280px,1fr] md:grid-rows-[1fr]">
            <LeftSider />
            <div className='relative min-h-0 min-w-0'>
              {children}
            </div>
          </div>
        </div>
      </DialogueContext>
    </div>
  )
}

function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  
  return (
    <html lang="en" className="h-full font-sans">
      <body className={`h-full font-sans`}>
        <ThemeProvider theme={joyTheme}>
          <CssVarsProvider theme={joyTheme} defaultMode="light">
            <CssWrapper>
              {children}
            </CssWrapper>
          </CssVarsProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}

export default RootLayout;