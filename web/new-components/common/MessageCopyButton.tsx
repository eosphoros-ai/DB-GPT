import { CheckOutlined, CopyOutlined } from '@ant-design/icons';
import { Tooltip, message } from 'antd';
import classNames from 'classnames';
import copy from 'copy-to-clipboard';
import React, { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';

/** Clipboard action shared by user messages and their reference cards. */
export default function MessageCopyButton({ text, label }: { text: string; label?: string }) {
  const { t } = useTranslation();
  const [copied, setCopied] = useState(false);
  const [copying, setCopying] = useState(false);
  const title = label || t('copy_to_clipboard');

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 2000);
    return () => clearTimeout(timer);
  }, [copied]);

  const handleCopy = async (event: React.MouseEvent<HTMLButtonElement>) => {
    event.stopPropagation();
    setCopying(true);
    try {
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        if (!copy(text)) throw new Error('Clipboard copy failed');
      }
      setCopied(true);
      message.success(t('copy_to_clipboard_success'));
    } catch {
      setCopied(false);
      message.error(t('copy_to_clipboard_failed'));
    } finally {
      setCopying(false);
    }
  };

  return (
    <Tooltip title={copied ? t('copy_success') : title}>
      <button
        type='button'
        aria-label={title}
        disabled={copying || !text}
        onClick={handleCopy}
        onKeyDown={event => event.stopPropagation()}
        className={classNames(
          'w-7 h-7 flex-shrink-0 inline-flex items-center justify-center rounded-md transition-colors',
          'text-[#8b8b84] dark:text-[#7c7972] hover:text-[#1c1c1a] dark:hover:text-[#e6e4df]',
          'hover:bg-[#f4f4f0] dark:hover:bg-white/[.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/40',
          copied && '!text-green-500',
        )}
      >
        {copied ? <CheckOutlined className='text-[15px]' /> : <CopyOutlined className='text-[15px]' />}
      </button>
    </Tooltip>
  );
}
