import { Box } from '@/lib/mui';

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <Box sx={{ color: 'red' }}>
      123
      {children}
    </Box>
  )
}
