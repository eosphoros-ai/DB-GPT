import { MenuOutlined, PlusOutlined, SettingOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import classNames from 'classnames';
import Image from 'next/image';
import React, { memo } from 'react';
import { useTranslation } from 'react-i18next';

interface ChatHeaderProps {
  title?: string;
  modelName?: string;
  onNewChat?: () => void;
  onOpenSettings?: () => void;
  onToggleSidebar?: () => void;
  showSidebarToggle?: boolean;
  extra?: React.ReactNode;
  className?: string;
}

const ChatHeader: React.FC<ChatHeaderProps> = ({
  title,
  modelName,
  onNewChat,
  onOpenSettings,
  onToggleSidebar,
  showSidebarToggle = false,
  extra,
  className,
}) => {
  const { t } = useTranslation();

  return (
    <header
      className={classNames(
        'flex items-center justify-between h-14 px-4 border-b',
        'bg-[var(--oc-background-strong)] border-[var(--oc-border-weak)]',
        'sticky top-0 z-10',
        className,
      )}
    >
      <div className='flex items-center gap-3'>
        {showSidebarToggle && (
          <button
            className={classNames(
              'flex items-center justify-center w-8 h-8 rounded-lg',
              'text-[var(--oc-icon-base)] hover:text-[var(--oc-icon-strong)]',
              'hover:bg-[var(--oc-surface-hover)] transition-colors',
            )}
            onClick={onToggleSidebar}
          >
            <MenuOutlined className='text-base' />
          </button>
        )}

        <div className='flex items-center gap-2'>
          <div className='flex items-center justify-center w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-blue-600'>
            <Image
              src='/pictures/logo.png'
              alt='中涣信息'
              width={20}
              height={20}
              className='object-contain'
              onError={e => {
                const target = e.target as HTMLImageElement;
                target.style.display = 'none';
              }}
            />
          </div>
          <div className='flex flex-col'>
            <span className='text-sm font-semibold text-[var(--oc-text-strong)]'>{title || '中涣信息'}</span>
            {modelName && <span className='text-xs text-[var(--oc-text-weak)]'>{modelName}</span>}
          </div>
        </div>
      </div>

      <div className='flex items-center gap-2'>
        {extra}

        {onNewChat && (
          <Tooltip title={t('new_chat')}>
            <button
              className={classNames(
                'flex items-center justify-center gap-1.5 h-8 px-3 rounded-lg',
                'text-sm font-medium',
                'bg-[var(--oc-interactive-base)] text-white',
                'hover:bg-[var(--oc-interactive-hover)] transition-colors',
              )}
              onClick={onNewChat}
            >
              <PlusOutlined className='text-xs' />
              <span className='hidden sm:inline'>{t('new_chat')}</span>
            </button>
          </Tooltip>
        )}

        {onOpenSettings && (
          <Tooltip title={t('settings', 'Settings')}>
            <button
              className={classNames(
                'flex items-center justify-center w-8 h-8 rounded-lg',
                'text-[var(--oc-icon-base)] hover:text-[var(--oc-icon-strong)]',
                'hover:bg-[var(--oc-surface-hover)] transition-colors',
              )}
              onClick={onOpenSettings}
            >
              <SettingOutlined className='text-base' />
            </button>
          </Tooltip>
        )}
      </div>
    </header>
  );
};

export default memo(ChatHeader);
