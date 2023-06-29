"use client";
import React, { useEffect, useMemo, useState } from 'react';
import { usePathname, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import Image from 'next/image';
import { Box, List, ListItem, ListItemButton, ListItemDecorator, ListItemContent, Typography, Button, useColorScheme } from '@/lib/mui';
import Article from '@mui/icons-material/Article';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import WbSunnyIcon from '@mui/icons-material/WbSunny';
import MenuIcon from '@mui/icons-material/Menu';
import AddIcon from '@mui/icons-material/Add';
import { useQueryDialog } from '@/hooks/useQueryDialogue';

const LeftSider =  () => {
  const pathname = usePathname();
	const { mode, setMode } = useColorScheme();
	const { dialogueList } = useQueryDialog();

	const menus = useMemo(() => {
		return [{
			label: 'Datastores',
			route: '/datastores',
			icon: <Article fontSize="small" />,
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
		<>
			<nav className='flex h-12 items-center justify-between border-b bg-gray-50 px-4 dark:border-gray-800 dark:bg-gray-800/70 md:hidden'>
				<div>
					<MenuIcon />
				</div>
				<span className='truncate px-4'>New Chat</span>
				<a href='' className='-mr-3 flex h-9 w-9 shrink-0 items-center justify-center'>
					<AddIcon />
				</a>
			</nav>
			<nav className="grid max-h-screen h-full max-md:hidden">
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
						<div className='flex items-center  gap-3'>
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
						<Link href={`/`}>
							<Button variant="outlined" color="primary" className='w-full'>+ 新建对话</Button>
						</Link>
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
									{dialogueList?.data?.map((each) => {
										const isSelect = pathname === `/agents/${each.conv_uid}`;
										return (
											<ListItem key={each.conv_uid}>
												<ListItemButton
													selected={isSelect}
													variant={isSelect ? 'soft' : 'plain'}
												>
													<ListItemContent>
														<Link href={`/agents/${each.conv_uid}`}>
															<Typography fontSize={14} noWrap={true}>
																{each?.user_name || each?.user_input || 'undefined'}
															</Typography>
														</Link>
													</ListItemContent>
												</ListItemButton>
											</ListItem>
										)
									})}
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
			</nav>
		</>
	)
};

export default LeftSider;