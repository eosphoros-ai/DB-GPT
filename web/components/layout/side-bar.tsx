import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, delDialogue } from '@/client/api';
import { STORAGE_LANG_KEY, STORAGE_THEME_KEY } from '@/utils';
import { DarkSvg, SunnySvg, ModelSvg } from '@/components/icons';
import { IChatDialogueSchema } from '@/types/chat';
import Icon, {
  ConsoleSqlOutlined,
  PartitionOutlined,
  DeleteOutlined,
  MessageOutlined,
  GlobalOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  PlusOutlined,
  ShareAltOutlined,
  MenuOutlined,
  SettingOutlined,
  BuildOutlined,
  ForkOutlined,
  AppstoreOutlined,
} from '@ant-design/icons';
import { Modal, message, Tooltip, Dropdown } from 'antd';
import { ItemType } from 'antd/es/menu/hooks/useItems';
import copy from 'copy-to-clipboard';
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
  onClick: () => void;
};

type RouteItem = {
  key: string;
  name: string;
  icon: ReactNode;
  path: string;
};

function menuItemStyle(active?: boolean) {
  return `flex items-center h-10 hover:bg-[#F1F5F9] dark:hover:bg-theme-dark text-base w-full transition-colors whitespace-nowrap px-4 ${
    active ? 'bg-[#F1F5F9] dark:bg-theme-dark' : ''
  }`;
}

function smallMenuItemStyle(active?: boolean) {
  return `flex items-center justify-center mx-auto rounded w-14 h-14 text-xl hover:bg-[#F1F5F9] dark:hover:bg-theme-dark transition-colors cursor-pointer ${
    active ? 'bg-[#F1F5F9] dark:bg-theme-dark' : ''
  }`;
}

function SideBar() {
  const { chatId, scene, isMenuExpand, dialogueList, queryDialogueList, refreshDialogList, setIsMenuExpand, setAgent, mode, setMode } =
    useContext(ChatContext);
  const { pathname, replace } = useRouter();
  const { t, i18n } = useTranslation();

  const [logo, setLogo] = useState<string>('/LOGO_1.png');

  const routes = useMemo(() => {
    const items: RouteItem[] = [
      {
        key: 'app',
        name: t('App'),
        path: '/app',
        icon: <AppstoreOutlined />,
      },
      {
        key: 'flow',
        name: t('awel_flow'),
        icon: <ForkOutlined />,
        path: '/flow',
      },
      {
        key: 'models',
        name: t('model_manage'),
        path: '/models',
        icon: <Icon component={ModelSvg} />,
      },
      {
        key: 'database',
        name: t('Database'),
        icon: <ConsoleSqlOutlined />,
        path: '/database',
      },
      {
        key: 'knowledge',
        name: t('Knowledge_Space'),
        icon: <PartitionOutlined />,
        path: '/knowledge',
      },
      {
        key: 'agent',
        name: t('Plugins'),
        path: '/agent',
        icon: <BuildOutlined />,
      },
      {
        key: 'prompt',
        name: t('Prompt'),
        icon: <MessageOutlined />,
        path: '/prompt',
      },
    ];
    return items;
  }, [i18n.language]);

  const handleToggleMenu = () => {
    setIsMenuExpand(!isMenuExpand);
  };

  const handleToggleTheme = useCallback(() => {
    const theme = mode === 'light' ? 'dark' : 'light';
    setMode(theme);
    localStorage.setItem(STORAGE_THEME_KEY, theme);
  }, [mode]);

  const handleChangeLang = useCallback(() => {
    const language = i18n.language === 'en' ? 'zh' : 'en';
    i18n.changeLanguage(language);
    localStorage.setItem(STORAGE_LANG_KEY, language);
  }, [i18n.language, i18n.changeLanguage]);

  const settings = useMemo(() => {
    const items: SettingItem[] = [
      {
        key: 'theme',
        name: t('Theme'),
        icon: mode === 'dark' ? <Icon component={DarkSvg} /> : <Icon component={SunnySvg} />,
        onClick: handleToggleTheme,
      },
      {
        key: 'language',
        name: t('language'),
        icon: <GlobalOutlined />,
        onClick: handleChangeLang,
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
  }, [mode, handleChangeLang, handleToggleMenu, handleChangeLang]);

  const dropDownRoutes: ItemType[] = useMemo(() => {
    return routes.map<ItemType>((item) => ({
      key: item.key,
      label: (
        <Link href={item.path} className="text-base">
          {item.icon}
          <span className="ml-2 text-sm">{item.name}</span>
        </Link>
      ),
    }));
  }, [routes]);

  const dropDownSettings: ItemType[] = useMemo(() => {
    return settings
      .filter((item) => !item.noDropdownItem)
      .map<ItemType>((item) => ({
        key: item.key,
        label: (
          <div className="text-base" onClick={item.onClick}>
            {item.icon}
            <span className="ml-2 text-sm">{item.name}</span>
          </div>
        ),
      }));
  }, [settings]);

  const handleDelChat = useCallback(
    (dialogue: IChatDialogueSchema) => {
      Modal.confirm({
        title: 'Delete Chat',
        content: 'Are you sure delete this chat?',
        width: '276px',
        centered: true,
        onOk() {
          return new Promise<void>(async (resolve, reject) => {
            try {
              const [err] = await apiInterceptors(delDialogue(dialogue.conv_uid));
              if (err) {
                reject();
                return;
              }
              message.success('success');
              refreshDialogList();
              dialogue.chat_mode === scene && dialogue.conv_uid === chatId && replace('/');
              resolve();
            } catch (e) {
              reject();
            }
          });
        },
      });
    },
    [refreshDialogList],
  );

  const handleClickChatItem = (item: IChatDialogueSchema) => {
    if (item.chat_mode === 'chat_agent' && item.select_param) {
      setAgent?.(item.select_param);
    }
  };

  const copyLink = useCallback((item: IChatDialogueSchema) => {
    const success = copy(`${location.origin}/chat?scene=${item.chat_mode}&id=${item.conv_uid}`);
    message[success ? 'success' : 'error'](success ? 'Copy success' : 'Copy failed');
  }, []);

  useEffect(() => {
    queryDialogueList();
  }, []);

  useEffect(() => {
    setLogo(mode === 'dark' ? '/WHITE_LOGO.png' : '/LOGO_1.png');
  }, [mode]);

  if (!isMenuExpand) {
    return (
      <div className="flex flex-col justify-between h-screen bg-white dark:bg-[#232734] animate-fade animate-duration-300">
        <Link href="/" className="px-2 py-3">
          <Image src="/LOGO_SMALL.png" alt="DB-GPT" width={63} height={46} className="w-[63px] h-[46px]" />
        </Link>
        <div>
          <Link href="/" className="flex items-center justify-center my-4 mx-auto w-12 h-12 bg-theme-primary rounded-full text-white">
            <PlusOutlined className="text-lg" />
          </Link>
        </div>
        {/* Chat List */}
        <div className="flex-1 overflow-y-scroll py-4 space-y-2">
          {dialogueList?.map((item) => {
            const active = item.conv_uid === chatId && item.chat_mode === scene;

            return (
              <Tooltip key={item.conv_uid} title={item.user_name || item.user_input} placement="right">
                <Link
                  href={`/chat?scene=${item.chat_mode}&id=${item.conv_uid}`}
                  className={smallMenuItemStyle(active)}
                  onClick={() => {
                    handleClickChatItem(item);
                  }}
                >
                  <MessageOutlined />
                </Link>
              </Tooltip>
            );
          })}
        </div>
        <div className="py-4">
          <Dropdown menu={{ items: dropDownRoutes }} placement="topRight">
            <div className={smallMenuItemStyle()}>
              <MenuOutlined />
            </div>
          </Dropdown>
          <Dropdown menu={{ items: dropDownSettings }} placement="topRight">
            <div className={smallMenuItemStyle()}>
              <SettingOutlined />
            </div>
          </Dropdown>
          {settings
            .filter((item) => item.noDropdownItem)
            .map((item) => (
              <Tooltip key={item.key} title={item.name} placement="right">
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
    <div className="flex flex-col h-screen bg-white dark:bg-[#232734]">
      {/* LOGO */}
      <Link href="/" className="p-2">
        <Image src={logo} alt="DB-GPT" width={239} height={60} className="w-full h-full" />
      </Link>
      <Link href="/" className="flex items-center justify-center mb-4 mx-4 h-11 bg-theme-primary rounded text-white">
        <PlusOutlined className="mr-2" />
        <span>{t('new_chat')}</span>
      </Link>
      {/* Chat List */}
      <div className="flex-1 overflow-y-scroll">
        {dialogueList?.map((item) => {
          const active = item.conv_uid === chatId && item.chat_mode === scene;

          return (
            <Link
              key={item.conv_uid}
              href={`/chat?scene=${item.chat_mode}&id=${item.conv_uid}`}
              className={`group/item ${menuItemStyle(active)}`}
              onClick={() => {
                handleClickChatItem(item);
              }}
            >
              <MessageOutlined className="text-base" />
              <div className="flex-1 line-clamp-1 mx-2 text-sm">{item.user_name || item.user_input}</div>
              <div
                className="group-hover/item:opacity-100 cursor-pointer opacity-0 mr-1"
                onClick={(e) => {
                  e.preventDefault();
                  copyLink(item);
                }}
              >
                <ShareAltOutlined />
              </div>
              <div
                className="group-hover/item:opacity-100 cursor-pointer opacity-0"
                onClick={(e) => {
                  e.preventDefault();
                  handleDelChat(item);
                }}
              >
                <DeleteOutlined />
              </div>
            </Link>
          );
        })}
      </div>
      {/* Settings */}
      <div className="pt-4">
        <div className="max-h-52 overflow-y-auto scrollbar-default">
          {routes.map((item) => (
            <Link key={item.key} href={item.path} className={`${menuItemStyle(pathname === item.path)} overflow-hidden`}>
              <>
                {item.icon}
                <span className="ml-3 text-sm">{item.name}</span>
              </>
            </Link>
          ))}
        </div>
        <div className="flex items-center justify-around py-4 mt-2">
          {settings.map((item) => (
            <Tooltip key={item.key} title={item.name}>
              <div className="flex-1 flex items-center justify-center cursor-pointer text-xl" onClick={item.onClick}>
                {item.icon}
              </div>
            </Tooltip>
          ))}
        </div>
      </div>
    </div>
  );
}

export default SideBar;
