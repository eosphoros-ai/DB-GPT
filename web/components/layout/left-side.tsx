'use client';
import React, { useState, useEffect, useMemo, useContext } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Modal } from 'antd';
import {
  Box,
  List,
  ListItem,
  ListItemButton,
  ListItemDecorator,
  ListItemContent,
  Typography,
  Button,
  useColorScheme,
  IconButton,
  Tooltip,
} from '@mui/joy';
import Article from '@mui/icons-material/Article';
import DarkModeIcon from '@mui/icons-material/DarkMode';
import WbSunnyIcon from '@mui/icons-material/WbSunny';
import SmsOutlinedIcon from '@mui/icons-material/SmsOutlined';
import DeleteOutlineOutlinedIcon from '@mui/icons-material/DeleteOutlineOutlined';
import Image from 'next/image';
import classNames from 'classnames';
import MenuIcon from '@mui/icons-material/Menu';
import DatasetIcon from '@mui/icons-material/Dataset';
import ExpandIcon from '@mui/icons-material/Expand';
import LanguageIcon from '@mui/icons-material/Language';
import ChatIcon from '@mui/icons-material/Chat';
import ModelTrainingIcon from '@mui/icons-material/ModelTraining';
import { useTranslation } from 'react-i18next';
import { ChatContext } from '@/app/chat-context';
import { DialogueListResponse } from '@/types/chat';
import { apiInterceptors, delDialogue } from '@/client/api';

const LeftSide = () => {
  const pathname = usePathname();
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [logoPath, setLogoPath] = useState('/LOGO_1.png');
  const { dialogueList, chatId, queryDialogueList, refreshDialogList, isMenuExpand, setIsMenuExpand } = useContext(ChatContext);
  const { mode, setMode } = useColorScheme();
  const menus = useMemo(() => {
    return [
      {
        label: t('Prompt'),
        route: '/prompt',
        icon: <ChatIcon fontSize="small" />,
        tooltip: t('Prompt'),
        active: pathname === '/prompt',
      },
      {
        label: t('Data_Source'),
        route: '/database',
        icon: <DatasetIcon fontSize="small" />,
        tooltip: t('Data_Source'),
        active: pathname === '/database',
      },
      {
        label: t('Knowledge_Space'),
        route: '/knowledge',
        icon: <Article fontSize="small" />,
        tooltip: t('Knowledge_Space'),
        active: pathname === '/knowledge',
      },
      {
        label: t('model_manage'),
        route: '/models',
        icon: <ModelTrainingIcon fontSize="small" />,
        tooltip: t('model_manage'),
        active: pathname === '/models',
      },
    ];
  }, [pathname, i18n.language]);

  function handleChangeTheme() {
    if (mode === 'light') {
      setMode('dark');
    } else {
      setMode('light');
    }
  }

  const handleChangeLanguage = () => {
    const language = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(language);
    window.localStorage.setItem('db_gpt_lng', language);
  };

  useEffect(() => {
    if (mode === 'light') {
      setLogoPath('/LOGO_1.png');
    } else {
      setLogoPath('/WHITE_LOGO.png');
    }
  }, [mode]);

  useEffect(() => {
    (async () => {
      await queryDialogueList();
    })();
  }, []);

  function expandMenu() {
    return (
      <>
        <Box className="p-2 gap-2 flex flex-row justify-between items-center">
          <div className="flex items-center gap-3">
            <Link href={'/'}>
              <Image src={logoPath} alt="DB-GPT" width={633} height={157} className="w-full max-w-full" />
            </Link>
          </div>
        </Box>
        <Box className="p-2">
          <Link href={`/`}>
            <Button
              color="primary"
              className="w-full bg-gradient-to-r from-[#31afff] to-[#1677ff] dark:bg-gradient-to-r dark:from-[#6a6a6a] dark:to-[#80868f]"
              style={{
                color: '#fff',
              }}
            >
              + New Chat
            </Button>
          </Link>
        </Box>
        <Box className="p-2 hidden xs:block sm:inline-block max-h-full overflow-auto">
          <List size="sm" sx={{ '--ListItem-radius': '8px' }}>
            <ListItem nested>
              <List
                size="sm"
                aria-labelledby="nav-list-browse"
                sx={{
                  '& .JoyListItemButton-root': { p: '8px' },
                  gap: '4px',
                }}
              >
                {(dialogueList || []).map((dialogue: DialogueListResponse[0]) => {
                  const isSelect = (pathname === `/chat` || pathname === '/chat/') && chatId === dialogue.conv_uid;
                  return (
                    <ListItem key={dialogue.conv_uid}>
                      <ListItemButton
                        selected={isSelect}
                        variant={isSelect ? 'soft' : 'plain'}
                        sx={{
                          '&:hover .del-btn': {
                            visibility: 'visible',
                          },
                        }}
                      >
                        <ListItemContent>
                          <Link href={`/chat?id=${dialogue.conv_uid}&scene=${dialogue?.chat_mode}`} className="flex items-center justify-between">
                            <Typography fontSize={14} noWrap={true}>
                              <SmsOutlinedIcon style={{ marginRight: '0.5rem' }} />
                              {dialogue?.user_name || dialogue?.user_input || 'undefined'}
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
                                    await apiInterceptors(delDialogue(dialogue.conv_uid));
                                    await refreshDialogList();
                                    if (pathname === `/chat` && chatId === dialogue.conv_uid) {
                                      router.push('/');
                                    }
                                  },
                                });
                              }}
                              className="del-btn invisible"
                            >
                              <DeleteOutlineOutlinedIcon />
                            </IconButton>
                          </Link>
                        </ListItemContent>
                      </ListItemButton>
                    </ListItem>
                  );
                })}
              </List>
            </ListItem>
          </List>
        </Box>
        <div className="flex flex-col justify-end flex-1">
          <Box className="p-2 pt-3 pb-6 border-t border-divider xs:block sticky bottom-0 z-100">
            <List size="sm" sx={{ '--ListItem-radius': '8px' }}>
              <ListItem nested>
                <List
                  size="sm"
                  aria-labelledby="nav-list-browse"
                  sx={{
                    '& .JoyListItemButton-root': { p: '8px' },
                  }}
                >
                  {menus.map((menu) => (
                    <Link key={menu.route} href={menu.route}>
                      <ListItem>
                        <ListItemButton
                          color="neutral"
                          sx={{ marginBottom: 1, height: '2.5rem' }}
                          selected={menu.active}
                          variant={menu.active ? 'soft' : 'plain'}
                        >
                          <ListItemDecorator
                            sx={{
                              color: menu.active ? 'inherit' : 'neutral.500',
                            }}
                          >
                            {menu.icon}
                          </ListItemDecorator>
                          <ListItemContent>{menu.label}</ListItemContent>
                        </ListItemButton>
                      </ListItem>
                    </Link>
                  ))}
                </List>
              </ListItem>
              <ListItem>
                <ListItemButton className="h-10" onClick={handleChangeTheme}>
                  <Tooltip title={t('Theme')}>
                    <ListItemDecorator>{mode === 'dark' ? <DarkModeIcon fontSize="small" /> : <WbSunnyIcon fontSize="small" />}</ListItemDecorator>
                  </Tooltip>
                  <ListItemContent>{t('Theme')}</ListItemContent>
                </ListItemButton>
              </ListItem>
              <ListItem>
                <ListItemButton className="h-10" onClick={handleChangeLanguage}>
                  <Tooltip title={t('language')}>
                    <ListItemDecorator className="text-2xl">
                      <LanguageIcon fontSize="small" />
                    </ListItemDecorator>
                  </Tooltip>
                  <ListItemContent>{t('language')}</ListItemContent>
                </ListItemButton>
              </ListItem>
              <ListItem>
                <ListItemButton
                  className="h-10"
                  onClick={() => {
                    setIsMenuExpand(false);
                  }}
                >
                  <Tooltip title={t('Close_Sidebar')}>
                    <ListItemDecorator className="text-2xl">
                      <ExpandIcon className="transform rotate-90" fontSize="small" />
                    </ListItemDecorator>
                  </Tooltip>
                  <ListItemContent>{t('Close_Sidebar')}</ListItemContent>
                </ListItemButton>
              </ListItem>
            </List>
          </Box>
        </div>
      </>
    );
  }

  function notExpandMenu() {
    return (
      <Box className="h-full py-6 flex flex-col justify-between">
        <Box className="flex justify-center items-center">
          <Tooltip title="Menu">
            <MenuIcon
              className="cursor-pointer text-2xl"
              onClick={() => {
                setIsMenuExpand(true);
              }}
            />
          </Tooltip>
        </Box>
        <Box className="flex flex-col gap-4 justify-center items-center">
          {menus.map((menu, index) => (
            <div className="flex justify-center text-2xl cursor-pointer" key={`menu_${index}`}>
              <Tooltip title={menu.tooltip}>{menu.icon}</Tooltip>
            </div>
          ))}
          <ListItem>
            <ListItemButton onClick={handleChangeTheme}>
              <Tooltip title={t('Theme')}>
                <ListItemDecorator className="text-2xl">
                  {mode === 'dark' ? <DarkModeIcon fontSize="small" /> : <WbSunnyIcon fontSize="small" />}
                </ListItemDecorator>
              </Tooltip>
            </ListItemButton>
          </ListItem>
          <ListItem>
            <ListItemButton onClick={handleChangeLanguage}>
              <Tooltip title={t('language')}>
                <ListItemDecorator className="text-2xl">
                  <LanguageIcon fontSize="small" />
                </ListItemDecorator>
              </Tooltip>
            </ListItemButton>
          </ListItem>
          <ListItem>
            <ListItemButton
              onClick={() => {
                setIsMenuExpand(true);
              }}
            >
              <Tooltip title={t('Open_Sidebar')}>
                <ListItemDecorator className="text-2xl">
                  <ExpandIcon className="transform rotate-90" fontSize="small" />
                </ListItemDecorator>
              </Tooltip>
            </ListItemButton>
          </ListItem>
        </Box>
      </Box>
    );
  }

  return (
    <>
      <nav className={classNames('grid max-h-screen h-full max-md:hidden')}>
        <Box className="flex flex-col border-r border-divider max-h-screen sticky left-0 top-0 overflow-hidden">
          {isMenuExpand ? expandMenu() : notExpandMenu()}
        </Box>
      </nav>
    </>
  );
};

export default LeftSide;
