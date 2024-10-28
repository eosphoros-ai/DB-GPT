import { ChatContext } from '@/app/chat-context';
import { DarkSvg, SunnySvg } from '@/components/icons';
import UserBar from '@/new-components/layout/UserBar';
import { STORAGE_LANG_KEY, STORAGE_THEME_KEY, STORAGE_USERINFO_KEY } from '@/utils/constants/index';
import Icon, { GlobalOutlined, MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { Popover, Tooltip } from 'antd';
import { ItemType } from 'antd/es/menu/hooks/useItems';
import cls from 'classnames';
import moment from 'moment';
import 'moment/locale/zh-cn';
import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type SettingItem = {
  key: string;
  name: string;
  icon: ReactNode;
  noDropdownItem?: boolean;
  onClick?: () => void;
  items?: ItemType[];
  onSelect?: (p: { key: string }) => void;
  defaultSelectedKeys?: string[];
  placement?: 'top' | 'topLeft';
};

type RouteItem = {
  key: string;
  name: string;
  icon: ReactNode;
  path: string;
  isActive?: boolean;
};

// TODO: unused function
// function menuItemStyle(active?: boolean) {
//   return `flex items-center h-12 hover:bg-[#F1F5F9] dark:hover:bg-theme-dark text-base w-full transition-colors whitespace-nowrap px-4 ${
//     active ? 'bg-[#F1F5F9] dark:bg-theme-dark' : ''
//   }`;
// }

function smallMenuItemStyle(active?: boolean) {
  return `flex items-center justify-center mx-auto rounded w-14 h-14 text-xl hover:bg-[#F1F5F9] dark:hover:bg-theme-dark transition-colors cursor-pointer ${
    active ? 'bg-[#F1F5F9] dark:bg-theme-dark' : ''
  }`;
}

function SideBar() {
  // const { chatId, scene, isMenuExpand, refreshDialogList, setIsMenuExpand, setAgent, mode, setMode, adminList } =
  //   useContext(ChatContext);
  const { isMenuExpand, setIsMenuExpand, mode, setMode, adminList } = useContext(ChatContext);
  const { pathname } = useRouter();
  const { t, i18n } = useTranslation();
  const [logo, setLogo] = useState<string>('/logo_zh_latest.png');

  const hasAdmin = useMemo(() => {
    const { user_id } = JSON.parse(localStorage.getItem(STORAGE_USERINFO_KEY) || '{}');
    return adminList.some(admin => admin.user_id === user_id);
  }, [adminList]);

  // TODO: unused function
  // const routes = useMemo(() => {
  //   const items: RouteItem[] = [
  //     {
  //       key: 'app',
  //       name: t('App'),
  //       path: '/app',
  //       icon: <AppstoreOutlined />,
  //     },
  //     {
  //       key: 'flow',
  //       name: t('awel_flow'),
  //       icon: <ForkOutlined />,
  //       path: '/flow',
  //     },
  //     {
  //       key: 'models',
  //       name: t('model_manage'),
  //       path: '/models',
  //       icon: <Icon component={ModelSvg} />,
  //     },
  //     {
  //       key: 'database',
  //       name: t('Database'),
  //       icon: <ConsoleSqlOutlined />,
  //       path: '/database',
  //     },
  //     {
  //       key: 'knowledge',
  //       name: t('Knowledge_Space'),
  //       icon: <PartitionOutlined />,
  //       path: '/knowledge',
  //     },
  //     {
  //       key: 'agent',
  //       name: t('Plugins'),
  //       path: '/agent',
  //       icon: <BuildOutlined />,
  //     },
  //     {
  //       key: 'prompt',
  //       name: t('Prompt'),
  //       icon: <MessageOutlined />,
  //       path: '/prompt',
  //     },
  //   ];
  //   return items;
  // }, [t]);

  const handleToggleMenu = useCallback(() => {
    setIsMenuExpand(!isMenuExpand);
  }, [isMenuExpand, setIsMenuExpand]);

  const handleToggleTheme = useCallback(() => {
    const theme = mode === 'light' ? 'dark' : 'light';
    setMode(theme);
    localStorage.setItem(STORAGE_THEME_KEY, theme);
  }, [mode, setMode]);

  const handleChangeLang = useCallback(() => {
    const language = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(language);
    if (language === 'zh') moment.locale('zh-cn');
    if (language === 'en') moment.locale('en');
    localStorage.setItem(STORAGE_LANG_KEY, language);
  }, [i18n]);
  const settings = useMemo(() => {
    const items: SettingItem[] = [
      {
        key: 'theme',
        name: t('Theme'),
        icon: mode === 'dark' ? <Icon component={DarkSvg} /> : <Icon component={SunnySvg} />,
        items: [
          {
            key: 'light',
            label: (
              <div className='py-1 flex justify-between gap-8 '>
                <span className='flex gap-2 items-center'>
                  <Image src='/pictures/theme_light.png' alt='english' width={38} height={32}></Image>
                  <span>Light</span>
                </span>
                <span
                  className={cls({
                    block: mode === 'light',
                    hidden: mode !== 'light',
                  })}
                >
                  ✓
                </span>
              </div>
            ),
          },
          {
            key: 'dark',
            label: (
              <div className='py-1 flex justify-between gap-8 '>
                <span className='flex gap-2 items-center'>
                  <Image src='/pictures/theme_dark.png' alt='english' width={38} height={32}></Image>
                  <span>Dark</span>
                </span>
                <span
                  className={cls({
                    block: mode === 'dark',
                    hidden: mode !== 'dark',
                  })}
                >
                  ✓
                </span>
              </div>
            ),
          },
        ],
        onClick: handleToggleTheme,
        onSelect: ({ key }: { key: string }) => {
          if (mode === key) return;
          setMode(key as 'light' | 'dark');
          localStorage.setItem(STORAGE_THEME_KEY, key);
        },
        defaultSelectedKeys: [mode],
        placement: 'topLeft',
      },
      {
        key: 'language',
        name: t('language'),
        icon: <GlobalOutlined />,
        items: [
          {
            key: 'en',
            label: (
              <div className='py-1 flex justify-between gap-8 '>
                <span className='flex gap-2'>
                  <Image src='/icons/english.png' alt='english' width={21} height={21}></Image>
                  <span>English</span>
                </span>
                <span
                  className={cls({
                    block: i18n.language === 'en',
                    hidden: i18n.language !== 'en',
                  })}
                >
                  ✓
                </span>
              </div>
            ),
          },
          {
            key: 'zh',
            label: (
              <div className='py-1 flex justify-between gap-8 '>
                <span className='flex gap-2'>
                  <Image src='/icons/zh.png' alt='english' width={21} height={21}></Image>
                  <span>简体中文</span>
                </span>
                <span
                  className={cls({
                    block: i18n.language === 'zh',
                    hidden: i18n.language !== 'zh',
                  })}
                >
                  ✓
                </span>
              </div>
            ),
          },
        ],
        onSelect: ({ key }: { key: string }) => {
          if (i18n.language === key) return;
          i18n.changeLanguage(key);
          if (key === 'zh') moment.locale('zh-cn');
          if (key === 'en') moment.locale('en');
          localStorage.setItem(STORAGE_LANG_KEY, key);
        },
        onClick: handleChangeLang,
        defaultSelectedKeys: [i18n.language],
      },
      {
        key: 'fold',
        name: t(isMenuExpand ? 'Close_Sidebar' : 'Show_Sidebar'),
        icon: isMenuExpand ? <MenuFoldOutlined /> : <MenuUnfoldOutlined />,
        onClick: handleToggleMenu,
        noDropdownItem: true,
      },
    ];
    return items;
  }, [t, mode, handleToggleTheme, i18n, handleChangeLang, isMenuExpand, handleToggleMenu, setMode]);

  const functions = useMemo(() => {
    const items: RouteItem[] = [
      {
        key: 'chat',
        name: t('chat_online'),
        icon: (
          <Image
            key='image_chat'
            src={pathname === '/chat' ? '/pictures/chat_active.png' : '/pictures/chat.png'}
            alt='chat_image'
            width={40}
            height={40}
          />
        ),
        path: '/chat',
        isActive: pathname.startsWith('/chat'),
      },
      {
        key: 'explore',
        name: t('explore'),
        isActive: pathname === '/',
        icon: (
          <Image
            key='image_explore'
            src={pathname === '/' ? '/pictures/explore_active.png' : '/pictures/explore.png'}
            alt='construct_image'
            width={40}
            height={40}
          />
        ),
        path: '/',
      },
      {
        key: 'construct',
        name: t('construct'),
        isActive: pathname.startsWith('/construct'),
        icon: (
          <Image
            key='image_construct'
            src={pathname.startsWith('/construct') ? '/pictures/app_active.png' : '/pictures/app.png'}
            alt='construct_image'
            width={40}
            height={40}
          />
        ),
        path: '/construct/app',
      },
    ];
    if (hasAdmin) {
      items.push({
        key: 'evaluation',
        name: '场景评测',
        icon: (
          <Image
            key='image_construct'
            src={pathname.startsWith('/evaluation') ? '/pictures/app_active.png' : '/pictures/app.png'}
            alt='construct_image'
            width={40}
            height={40}
          />
        ),
        path: '/evaluation',
        isActive: pathname === '/evaluation',
      });
    }
    return items;
  }, [t, pathname, hasAdmin]);

  // TODO: unused function
  // const dropDownRoutes: ItemType[] = useMemo(() => {
  //   return routes.map<ItemType>(item => ({
  //     key: item.key,
  //     label: (
  //       <Link href={item.path} className='text-base'>
  //         {item.icon}
  //         <span className='ml-2 text-sm'>{item.name}</span>
  //       </Link>
  //     ),
  //   }));
  // }, [routes]);

  // TODO: unused function
  // const dropDownSettings: ItemType[] = useMemo(() => {
  //   return settings
  //     .filter(item => !item.noDropdownItem)
  //     .map<ItemType>(item => ({
  //       key: item.key,
  //       label: (
  //         <div className='text-base' onClick={item.onClick}>
  //           {item.icon}
  //           <span className='ml-2 text-sm'>{item.name}</span>
  //         </div>
  //       ),
  //     }));
  // }, [settings]);

  // TODO: unused function
  // const dropDownFunctions: ItemType[] = useMemo(() => {
  //   return functions.map<ItemType>(item => ({
  //     key: item.key,
  //     label: (
  //       <Link href={item.path} className='text-base'>
  //         {item.icon}
  //         <span className='ml-2 text-sm'>{item.name}</span>
  //       </Link>
  //     ),
  //   }));
  // }, [functions]);

  // TODO: unused function
  // const handleDelChat = useCallback(
  //   (dialogue: IChatDialogueSchema) => {
  //     Modal.confirm({
  //       title: 'Delete Chat',
  //       content: 'Are you sure delete this chat?',
  //       width: '276px',
  //       centered: true,
  //       onOk() {
  //         return new Promise<void>(async (resolve, reject) => {
  //           try {
  //             const [err] = await apiInterceptors(delDialogue(dialogue.conv_uid));
  //             if (err) {
  //               reject();
  //               return;
  //             }
  //             message.success('success');
  //             refreshDialogList();
  //             dialogue.chat_mode === scene && dialogue.conv_uid === chatId && replace('/');
  //             resolve();
  //           } catch (e) {
  //             reject();
  //           }
  //         });
  //       },
  //     });
  //   },
  //   [chatId, refreshDialogList, replace, scene],
  // );

  // TODO: unused function
  // const handleClickChatItem = (item: IChatDialogueSchema) => {
  //   if (item.chat_mode === 'chat_agent' && item.select_param) {
  //     setAgent?.(item.select_param);
  //   }
  // };

  // TODO: unused function
  // const copyLink = useCallback((item: IChatDialogueSchema) => {
  //   const success = copy(`${location.origin}/chat?scene=${item.chat_mode}&id=${item.conv_uid}`);
  //   message[success ? 'success' : 'error'](success ? 'Copy success' : 'Copy failed');
  // }, []);

  // useEffect(() => {
  //   queryDialogueList();
  // }, [queryDialogueList]);

  useEffect(() => {
    const language = i18n.language;
    if (language === 'zh') moment.locale('zh-cn');
    if (language === 'en') moment.locale('en');
  }, []);

  useEffect(() => {
    setLogo(mode === 'dark' ? '/logo_s_latest.png' : '/logo_zh_latest.png');
  }, [mode]);

  if (!isMenuExpand) {
    return (
      <div
        className='flex flex-col justify-between pt-4 h-screen bg-bar dark:bg-[#232734] animate-fade animate-duration-300'
        // onMouseEnter={() => {
        // setIsMenuExpand(true);
        // }}
      >
        <div>
          <Link href='/' className='flex justify-center items-center pb-4'>
            <Image src={isMenuExpand ? logo : '/LOGO_SMALL.png'} alt='DB-GPT' width={40} height={40} />
          </Link>
          <div className='flex flex-col gap-4 items-center'>
            {functions.map(i => (
              <Link key={i.key} className='h-12 flex items-center' href={i.path}>
                {i?.icon}
              </Link>
            ))}
          </div>
        </div>
        <div className='py-4'>
          <UserBar onlyAvatar />
          {settings
            .filter(item => item.noDropdownItem)
            .map(item => (
              <Tooltip key={item.key} title={item.name} placement='right'>
                <div className={smallMenuItemStyle()} onClick={item.onClick}>
                  {item.icon}
                </div>
              </Tooltip>
            ))}
        </div>
      </div>
    );
  }

  return (
    <div
      className='flex flex-col justify-between h-screen px-4 pt-4 bg-bar dark:bg-[#232734] animate-fade animate-duration-300'
      // onMouseLeave={() => {
      //   setIsMenuExpand(false);
      // }}
    >
      <div>
        {/* LOGO */}
        <Link href='/' className='flex items-center justify-center p-2 pb-4'>
          <Image src={isMenuExpand ? logo : '/LOGO_SMALL.png'} alt='DB-GPT' width={180} height={40} />
        </Link>
        {/* functions */}
        <div className='flex flex-col gap-4'>
          {functions.map(item => {
            return (
              <Link
                href={item.path}
                className={cls(
                  'flex items-center w-full h-12 px-4 cursor-pointer hover:bg-[#F1F5F9] dark:hover:bg-theme-dark hover:rounded-xl',
                  {
                    'bg-white rounded-xl dark:bg-black': item.isActive,
                  },
                )}
                key={item.key}
              >
                <div className='mr-3'>{item.icon}</div>
                <span className='text-sm'>{t(item.name as any)}</span>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Settings */}
      <div className='pt-4'>
        <span className={cls('flex items-center w-full h-12 px-4 bg-[#F1F5F9] dark:bg-theme-dark rounded-xl')}>
          <div className='mr-3 w-full'>
            <UserBar />
          </div>
        </span>
        <div className='flex items-center justify-around py-4 mt-2 border-t border-dashed border-gray-200 dark:border-gray-700'>
          {settings.map(item => (
            <div key={item.key}>
              <Popover content={item.name}>
                <div className='flex-1 flex items-center justify-center cursor-pointer text-xl' onClick={item.onClick}>
                  {item.icon}
                </div>
              </Popover>
              {/* {item.items ? (
                <Dropdown
                  menu={{ items: item.items, selectable: true, onSelect: item.onSelect, defaultSelectedKeys: item.defaultSelectedKeys }}
                  placement={item.placement || 'top'}
                  arrow
                >
                  <span onClick={item.onClick}>{item.icon}</span>
                </Dropdown>
              ) : (
                <Popover content={item.name}>
                  <div className="flex-1 flex items-center justify-center cursor-pointer text-xl" onClick={item.onClick}>
                    {item.icon}
                  </div>
                </Popover>
              )} */}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default SideBar;
