"use client";
import React, { useEffect, useMemo } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Modal } from 'antd';
import { Box, List, ListItem, ListItemButton, ListItemDecorator, ListItemContent, Typography, Button, useColorScheme, IconButton } from '@/lib/mui';
import Article from '@mui/icons-material/Article';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import WbSunnyIcon from '@mui/icons-material/WbSunny';
import MenuIcon from '@mui/icons-material/Menu';
import AddIcon from '@mui/icons-material/Add';
import SmsOutlinedIcon from '@mui/icons-material/SmsOutlined';import { useDialogueContext } from '@/app/context/dialogue';
import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import { sendPostRequest } from '@/utils/request';

const LeftSider =  () => {
  const pathname = usePathname();
  const searchParams = useSearchParams();
	const id = searchParams.get('id');
	const router = useRouter();
	const { dialogueList, queryDialogueList, refreshDialogList } = useDialogueContext();
	const { mode, setMode } = useColorScheme();

	const menus = useMemo(() => {
		return [{
			label: 'Knowledge Space',
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

	useEffect(() => {
		(async () => {
			await queryDialogueList();
		})();
	}, []);

	return (
		<>
			<nav className='flex h-12 items-center justify-between border-b px-4 dark:border-gray-800 dark:bg-gray-800/70 md:hidden'>
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
							<Button
								color="primary"
								className='w-full bg-gradient-to-r from-[#31afff] to-[#1677ff] dark:bg-gradient-to-r dark:from-[#6a6a6a] dark:to-[#80868f]'
								style={{
									color: '#fff'
								}}
							>
								+ New Chat
							</Button>
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
										gap: '4px'
									}}
								>
									{dialogueList?.data?.map((each) => {
										const isSelect = (pathname === `/chat` || pathname === '/chat/') && id === each.conv_uid;
										return (
											<ListItem key={each.conv_uid}>
												<ListItemButton
													selected={isSelect}
													variant={isSelect ? 'soft' : 'plain'}
													sx={{
														'&:hover .del-btn': {
															visibility: 'visible'
														}
													}}
												>
													<ListItemContent>
														<Link href={`/chat?id=${each.conv_uid}&scene=${each?.chat_mode}`} className="flex items-center justify-between">
															<Typography fontSize={14} noWrap={true}>
																<SmsOutlinedIcon style={{ marginRight: '0.5rem' }} />
																{each?.user_name || each?.user_input || 'undefined'}
															</Typography>
															<IconButton
																color="neutral"
																variant="plain"
																size="sm"
																onClick={(e) => {
																	e.preventDefault();
																	e.stopPropagation();
																	Modal.confirm({
																		title: 'Delete Chat',
																		content: 'Are you sure delete this chat?',
																		width: '276px',
																		centered: true,
																		async onOk() {
																			await sendPostRequest(`/v1/chat/dialogue/delete?con_uid=${each.conv_uid}`);
																			await refreshDialogList();
																			if (pathname === `/chat` && searchParams.get('id') === each.conv_uid) {
																				router.push('/');
																			}
																		}
																	})
																}}
																className='del-btn invisible'
															>
																<DeleteOutlineOutlinedIcon />
															</IconButton>
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
								pt: 3,
								pb: 6,
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
														sx={{ marginBottom: 1, height: '2.5rem' }}
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
										sx={{ height: '2.5rem' }}
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