"use client"
import './globals.css'
import './nprogress.css';
import LeftSider from '@/components/leftSider';
import { CssVarsProvider, ThemeProvider } from '@mui/joy/styles';
import { joyTheme } from './defaultTheme';
import TopProgressBar from '@/components/topProgressBar';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="h-full font-sans">
      <body className={`h-full font-sans`}>
        <ThemeProvider theme={joyTheme}>
          <CssVarsProvider theme={joyTheme} defaultMode="light">
            <TopProgressBar />
              <div className={`contents h-full`}>
                <div className="grid h-full w-screen grid-cols-1 grid-rows-[auto,1fr] overflow-hidden text-smd dark:text-gray-300 md:grid-cols-[280px,1fr] md:grid-rows-[1fr]">
                  <LeftSider />
                  <div className='relative min-h-0 min-w-0'>
                    {children}
                  </div>
                </div>
              </div>
          </CssVarsProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
