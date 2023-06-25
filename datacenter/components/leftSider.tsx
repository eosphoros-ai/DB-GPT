"use client";
import React, { useMemo } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { Box, List, ListItem, ListItemButton, ListItemDecorator, ListItemContent } from '@/lib/mui';
import SmartToyRoundedIcon from '@mui/icons-material/SmartToyRounded'; // Icons import
import StorageRoundedIcon from '@mui/icons-material/StorageRounded';

const LeftSider =  () => {
  const pathname = usePathname();
	console.log(pathname, 'router')
	const menus = useMemo(() => {
		return [{
			label: 'Agents',
			icon: <SmartToyRoundedIcon fontSize="small" />,
			route: '/agents',
			active: pathname === '/agents',
		}, {
			label: 'Datastores',
			route: '/',
			icon: <StorageRoundedIcon fontSize="small" />,
			active: pathname === '/'
		}];
	}, [pathname]);

	return (
		<Box 
			sx={[
				{
					p: 2,
					borderRight: '1px solid',
					borderColor: 'divider',
					display: {
						xs: 'none',
						sm: 'initial',
					},
				},
			]}
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
										selected={each.active}
										variant={each.active ? 'soft' : 'plain'}
									>
										<ListItemDecorator
											sx={{ 
												color: each.active ? 'inherit' : 'neutral.500',
												'--ListItemDecorator-size': '26px'
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
			</List>
		</Box>
	)
};

export default LeftSider;