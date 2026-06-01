import { DatabaseOutlined, FileTextOutlined, RobotOutlined, ThunderboltOutlined } from '@ant-design/icons';
import classNames from 'classnames';
import Image from 'next/image';
import React, { memo } from 'react';
import { useTranslation } from 'react-i18next';

interface SuggestionItem {
  icon: React.ReactNode;
  title: string;
  description: string;
  onClick?: () => void;
}

interface ChatWelcomeProps {
  userName?: string;
  suggestions?: SuggestionItem[];
  onSuggestionClick?: (suggestion: SuggestionItem) => void;
  className?: string;
  children?: React.ReactNode;
}

const defaultSuggestions: SuggestionItem[] = [
  {
    icon: <DatabaseOutlined className='text-blue-500' />,
    title: 'Database Analysis',
    description: 'Connect to your database and explore data with natural language',
  },
  {
    icon: <FileTextOutlined className='text-green-500' />,
    title: 'Knowledge Base',
    description: 'Chat with your documents and knowledge base',
  },
  {
    icon: <ThunderboltOutlined className='text-amber-500' />,
    title: 'Agent Tasks',
    description: 'Let AI agents help you complete complex tasks',
  },
  {
    icon: <RobotOutlined className='text-purple-500' />,
    title: 'Code Assistant',
    description: 'Get help with coding, debugging, and code review',
  },
];

const ChatWelcome: React.FC<ChatWelcomeProps> = ({
  userName,
  suggestions = defaultSuggestions,
  onSuggestionClick,
  className,
  children,
}) => {
  const { t } = useTranslation();

  const getGreeting = (): string => {
    const hour = new Date().getHours();
    if (hour < 12) return String(t('good_morning', 'Good morning'));
    if (hour < 18) return String(t('good_afternoon', 'Good afternoon'));
    return String(t('good_evening', 'Good evening'));
  };

  return (
    <div
      className={classNames(
        'flex flex-col items-center justify-center min-h-[60vh] px-4 py-12',
        'oc-animate-fade-in',
        className,
      )}
    >
      <div className='flex flex-col items-center max-w-2xl w-full'>
        <div className='flex items-center justify-center w-20 h-20 mb-6 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-600 shadow-lg'>
          <Image
            src='/pictures/logo.png'
            alt='中涣信息'
            width={48}
            height={48}
            className='object-contain'
            onError={e => {
              const target = e.target as HTMLImageElement;
              target.style.display = 'none';
            }}
          />
        </div>

        <h1 className='text-2xl sm:text-3xl font-semibold text-[var(--oc-text-strong)] mb-2 text-center'>
          {getGreeting()}
          {userName ? `, ${userName}` : ''}
        </h1>

        <p className='text-base text-[var(--oc-text-weak)] mb-8 text-center max-w-md'>
          {t('welcome_message', 'How can I help you today? Ask me anything or try one of the suggestions below.')}
        </p>

        {children}

        <div className='grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-xl'>
          {suggestions.map((suggestion, index) => (
            <button
              key={index}
              className={classNames(
                'flex items-start gap-3 p-4 rounded-xl text-left',
                'bg-[var(--oc-surface-raised)] border border-[var(--oc-border-weak)]',
                'hover:border-[var(--oc-border-base)] hover:shadow-md',
                'transition-all duration-200',
                'group',
              )}
              onClick={() => {
                suggestion.onClick?.();
                onSuggestionClick?.(suggestion);
              }}
            >
              <div
                className={classNames(
                  'flex items-center justify-center w-10 h-10 rounded-lg flex-shrink-0',
                  'bg-[var(--oc-surface-base)] group-hover:bg-[var(--oc-surface-hover)]',
                  'transition-colors',
                )}
              >
                {suggestion.icon}
              </div>
              <div className='flex flex-col min-w-0'>
                <span className='text-sm font-medium text-[var(--oc-text-strong)] truncate'>{suggestion.title}</span>
                <span className='text-xs text-[var(--oc-text-weak)] line-clamp-2'>{suggestion.description}</span>
              </div>
            </button>
          ))}
        </div>

        <div className='mt-8 flex items-center gap-2 text-xs text-[var(--oc-text-weaker)]'>
          <span>Powered by</span>
          <span className='font-medium text-[var(--oc-text-weak)]'>中涣信息</span>
        </div>
      </div>
    </div>
  );
};

export default memo(ChatWelcome);
