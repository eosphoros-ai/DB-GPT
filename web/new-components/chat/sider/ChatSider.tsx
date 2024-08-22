import { ChatContext } from '@/app/chat-context';
import { apiInterceptors, delDialogue } from '@/client/api';
import { IChatDialogueSchema } from '@/types/chat';
import { CaretLeftOutlined, CaretRightOutlined, DeleteOutlined, ShareAltOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { Flex, Layout, Modal, Spin, Tooltip, Typography, message } from 'antd';
import copy from 'copy-to-clipboard';
import Image from 'next/image';
import { useRouter, useSearchParams } from 'next/navigation';
import React, { useContext, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import AppDefaultIcon from '../../common/AppDefaultIcon';

const { Sider } = Layout;

const zeroWidthTriggerDefaultStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 16,
  height: 48,
  position: 'absolute',
  top: '50%',
  transform: 'translateY(-50%)',
  border: '1px solid #d6d8da',
  borderRadius: 8,
  right: -8,
};

/**
 *
 * 会话项
 */
const MenuItem: React.FC<{ item: any; refresh?: any; order: React.MutableRefObject<number>; historyLoading?: boolean }> = ({
  item,
  refresh,
  historyLoading,
  order,
}) => {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const chatId = searchParams?.get('id') ?? '';
  const scene = searchParams?.get('scene') ?? '';

  const { setCurrentDialogInfo } = useContext(ChatContext);

  // 当前活跃会话
  const active = useMemo(() => {
    if (item.default) {
      return item.default && !chatId && !scene;
    } else {
      return item.conv_uid === chatId && item.chat_mode === scene;
    }
  }, [chatId, scene, item]);

  // 删除会话
  const handleDelChat = () => {
    Modal.confirm({
      title: t('delete_chat'),
      content: t('delete_chat_confirm'),
      centered: true,
      onOk: async () => {
        const [err] = await apiInterceptors(delDialogue(item.conv_uid));
        if (err) {
          return;
        }
        await refresh?.();
        if (item.conv_uid === chatId) {
          router.push(`/chat`);
        }
      },
    });
  };

  return (
    <Flex
      align="center"
      className={`group/item w-full h-12 p-3 rounded-lg  hover:bg-white dark:hover:bg-theme-dark cursor-pointer mb-2 relative ${
        active ? 'bg-white dark:bg-theme-dark bg-opacity-100' : ''
      }`}
      onClick={() => {
        if (historyLoading) {
          return;
        }
        !item.default &&
          setCurrentDialogInfo?.({
            chat_scene: item.chat_mode,
            app_code: item.app_code,
          });
        localStorage.setItem(
          'cur_dialog_info',
          JSON.stringify({
            chat_scene: item.chat_mode,
            app_code: item.app_code,
          }),
        );
        router.push(item.default ? '/chat' : `?scene=${item.chat_mode}&id=${item.conv_uid}`);
      }}
    >
      <Tooltip title={item.chat_mode}>
        <div className="flex items-center justify-center w-8 h-8 rounded-lg mr-3 bg-white">{item.icon}</div>
      </Tooltip>
      <div className="flex flex-1 line-clamp-1">
        <Typography.Text
          ellipsis={{
            tooltip: true,
          }}
        >
          {item.label}
        </Typography.Text>
      </div>
      {!item.default && (
        <div className="flex gap-1 ml-1">
          <div
            className="group-hover/item:opacity-100 cursor-pointer opacity-0"
            onClick={(e) => {
              e.stopPropagation();
            }}
          >
            <ShareAltOutlined
              style={{ fontSize: 16 }}
              onClick={() => {
                const success = copy(`${location.origin}/chat?scene=${item.chat_mode}&id=${item.conv_uid}`);
                message[success ? 'success' : 'error'](success ? t('copy_success') : t('copy_failed'));
              }}
            />
          </div>
          <div
            className="group-hover/item:opacity-100 cursor-pointer opacity-0"
            onClick={(e) => {
              e.stopPropagation();
              handleDelChat();
            }}
          >
            <DeleteOutlined style={{ fontSize: 16 }} />
          </div>
        </div>
      )}
      <div
        className={` w-1 rounded-sm bg-[#0c75fc] absolute top-1/2 left-0 -translate-y-1/2 transition-all duration-500 ease-in-out ${
          active ? 'h-5' : 'w-0 h-0'
        }`}
      />
    </Flex>
  );
};

const ChatSider: React.FC<{
  dialogueList: any;
  refresh: () => void;
  historyLoading: boolean;
  listLoading: boolean;
  order: React.MutableRefObject<number>;
}> = ({ dialogueList = [], refresh, historyLoading, listLoading, order }) => {
  const searchParams = useSearchParams();
  const scene = searchParams?.get('scene') ?? '';
  const { t } = useTranslation();
  const { mode } = useContext(ChatContext);
  const [collapsed, setCollapsed] = useState<boolean>(scene === 'chat_dashboard');

  // 展开或收起列表按钮样式
  const triggerStyle: React.CSSProperties = useMemo(() => {
    if (collapsed) {
      return {
        ...zeroWidthTriggerDefaultStyle,
        right: -16,
        borderRadius: '0px 8px 8px 0',
        borderLeft: '1px solid #d5e5f6',
      };
    }
    return {
      ...zeroWidthTriggerDefaultStyle,
      borderLeft: '1px solid #d6d8da',
    };
  }, [collapsed]);

  // 会话列表配置项
  const items: MenuProps['items'] = useMemo(() => {
    const list = dialogueList[1] || [];
    if (list?.length > 0) {
      return list.map((item: IChatDialogueSchema) => ({
        ...item,
        label: item.user_input || item.select_param,
        key: item.conv_uid,
        icon: <AppDefaultIcon scene={item.chat_mode} />,
        default: false,
      }));
    }
    return [];
  }, [dialogueList]);

  return (
    <Sider
      className="bg-[#ffffff80]  border-r  border-[#d5e5f6] dark:bg-[#ffffff29] dark:border-[#ffffff66]"
      theme={mode}
      width={280}
      collapsible={true}
      collapsed={collapsed}
      collapsedWidth={0}
      trigger={collapsed ? <CaretRightOutlined className="text-base" /> : <CaretLeftOutlined className="text-base" />}
      zeroWidthTriggerStyle={triggerStyle}
      onCollapse={(collapsed) => setCollapsed(collapsed)}
    >
      <div className="flex flex-col h-full w-full bg-transparent px-4 pt-6  ">
        <div className="w-full text-base font-semibold text-[#1c2533] dark:text-[rgba(255,255,255,0.85)] mb-4 line-clamp-1">{t('dialog_list')}</div>
        <Flex flex={1} vertical={true} className="overflow-y-auto">
          <MenuItem
            item={{
              label: t('assistant'),
              key: 'default',
              icon: <Image src="/LOGO_SMALL.png" alt="default" width={24} height={24} className='flex-1' />,
              default: true,
            }}
            order={order}
          />
          <Spin spinning={listLoading} className="mt-2">
            {!!items?.length &&
              items.map((item) => <MenuItem key={item?.key} item={item} refresh={refresh} historyLoading={historyLoading} order={order} />)}
          </Spin>
        </Flex>
      </div>
    </Sider>
  );
};

export default ChatSider;
