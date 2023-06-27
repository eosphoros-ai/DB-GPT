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
    <html lang="en" className="min-h-full font-sans">
      <body className={`min-h-screen font-sans`}>
        <ThemeProvider theme={joyTheme}>
          <CssVarsProvider theme={joyTheme} defaultMode="light">
            <TopProgressBar />
            <div className='min-h-screen flex flex-col'>
              <div className="flex flex-1 flex-row">
                <LeftSider />
                <div className='flex-1 overflow-auto'>{children}</div>
              </div>
            </div>
          </CssVarsProvider>
        </ThemeProvider>
      </body>
    </html>
  )
}
