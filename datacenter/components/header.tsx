import { Box, Typography } from '@/lib/mui';
import Image from 'next/image';
import ColorSchemeToggle from './colorSchemeToggle';

const Header =  () => {
	return (
		<Box
			sx={{
				p: 2,
				gap: 2,
				display: 'flex',
				flexDirection: 'row',
				justifyContent: 'space-between',
				alignItems: 'center',
				gridColumn: '1 / -1',
				borderBottom: '1px solid',
				borderColor: 'divider',
				position: 'sticky',
				top: 0,
				zIndex: 1100,
				background: 'var(--joy-palette-background-body)'
			}}
		>
			<div className='flex items-center justify-center gap-3'>
				<Image
					src="/databerry-logo-icon.png"
					width="200"
					height="200"
					className='w-12'
					alt="Databerry"
				/>
				<Typography component="h1" fontWeight="xl">
					DB-GPT
				</Typography>
			</div>
			<div>
				<ColorSchemeToggle />
			</div>
		</Box>
	)
};

export default Header;