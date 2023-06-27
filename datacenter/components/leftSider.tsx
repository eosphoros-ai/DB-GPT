"use client";
import React, { useMemo, useState } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { Box, List, ListItem, ListItemButton, ListItemDecorator, ListItemContent, Typography, Button, useColorScheme } from '@/lib/mui';
import SmartToyRoundedIcon from '@mui/icons-material/SmartToyRounded'; // Icons import
import StorageRoundedIcon from '@mui/icons-material/StorageRounded';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import WbSunnyIcon from '@mui/icons-material/WbSunny';

const mockHistory = [{
	id: 1,
	summary: "chat1",
	history: [{
		from: 'human',
		message: 'Hello'
	}, {
		from: 'agent',
		message: 'Hello! How can I assist you today?'
	}]
}, {
	id: 2,
	summary: "天气",
	history: [{
		from: 'human',
		message: '讲个笑话'
	}, {
		from: 'agent',
		message: '当然！这是一个经典的笑话：xxx'
	}]
}];

const LeftSider =  () => {
  const pathname = usePathname();
	const { mode, setMode } = useColorScheme();
	const [chatSelect, setChatSelect] = useState();
	const menus = useMemo(() => {
		return [{
			label: 'Agents',
			icon: <SmartToyRoundedIcon fontSize="small" />,
			route: '/agents',
			active: pathname === '/agents',
		}, {
			label: 'Datastores',
			route: '/datastores',
			icon: <StorageRoundedIcon fontSize="small" />,
			active: pathname === '/datastores'
		}];
	}, [pathname]);

	const handleChangeTheme = () => {
		if (mode === 'light') {
			setMode('dark');
		} else {
			setMode('light');
		}
	};

	return (
		<Box
			sx={{
				display: 'flex',
				flexDirection: 'column',
				borderRight: '1px solid',
				borderColor: 'divider',
				maxHeight: '100vh',
				position: 'sticky',
				left: '0px',
				top: '0px',
				overflow: 'hidden',
			}}
		>
			<Box
				sx={{
					p: 2,
					gap: 2,
					display: 'flex',
					flexDirection: 'row',
					justifyContent: 'space-between',
					alignItems: 'center',
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
			</Box>
			<Box
				sx={{
					px: 2
				}}
			>
				<Button variant="outlined" color="primary" className='w-full'>+ 新建对话</Button>
			</Box>
			<Box
				sx={{
					p: 2,
					display: {
						xs: 'none',
						sm: 'initial',
					},
					maxHeight: '100%',
					overflow: 'auto',
				}}
			>
				<List size="sm" sx={{ '--ListItem-radius': '8px' }}>
					<ListItem nested>
						<List
							size="sm"
							aria-labelledby="nav-list-browse"
							sx={{
								'& .JoyListItemButton-root': { p: '8px' },
							}}
						>
							{mockHistory.map((each, index) => (
								<ListItem key={index}>
									<ListItemButton
										selected={chatSelect === each.id}
										variant={chatSelect === each.id ? 'soft' : 'plain'}
										onClick={() => {
											setChatSelect(each.id);
										}}
									>
										<ListItemContent>{each.summary}</ListItemContent>
									</ListItemButton>
								</ListItem>
							))}
						</List>
					</ListItem>
				</List>
			</Box>
			<div className='flex flex-col justify-between flex-1'>
				<div></div>
				<Box
					sx={{
						p: 2,
						borderTop: '1px solid',
						borderColor: 'divider',
						display: {
							xs: 'none',
							sm: 'initial',
						},
						position: 'sticky',
						bottom: 0,
						zIndex: 100,
						background: 'var(--joy-palette-background-body)'
					}}
				>
					<List size="sm" sx={{ '--ListItem-radius': '8px' }}>
						<ListItem nested>
							<List
								size="sm"
								aria-labelledby="nav-list-browse"
								sx={{
									'& .JoyListItemButton-root': { p: '8px' },
								}}
							>
								{menus.map((each) => (
									<Link key={each.route} href={each.route}>
										<ListItem>
											<ListItemButton
												color="neutral"
												selected={each.active}
												variant={each.active ? 'soft' : 'plain'}
											>
												<ListItemDecorator
													sx={{ 
														color: each.active ? 'inherit' : 'neutral.500',
													}}
												>
													{each.icon}
												</ListItemDecorator>
												<ListItemContent>{each.label}</ListItemContent>
											</ListItemButton>
										</ListItem>
									</Link>
								))}
							</List>
						</ListItem>
						<ListItem>
							<ListItemButton
								onClick={handleChangeTheme}
							>
								<ListItemDecorator>
									{mode === 'dark' ? (
										<DarkModeIcon fontSize="small"/>
									) : (
										<WbSunnyIcon fontSize="small"/>
									)}
								</ListItemDecorator>
								<ListItemContent>Theme</ListItemContent>
							</ListItemButton>
						</ListItem>
					</List>
				</Box>
			</div>
			
		</Box>
	)
};

export default LeftSider;