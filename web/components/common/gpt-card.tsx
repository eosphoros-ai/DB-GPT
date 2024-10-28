import { Popover, Tag, TagProps, Tooltip } from 'antd';
import classNames from 'classnames';
import Image from 'next/image';
import { HtmlHTMLAttributes, PropsWithChildren, ReactNode, memo, useMemo } from 'react';

interface Props {
  title: string;
  desc?: string;
  disabled?: boolean;
  tags?: (
    | string
    | {
        text: ReactNode;
        /** @default false */
        border?: boolean;
        /** @default default */
        color?: TagProps['color'];
      }
  )[];
  operations?: {
    children: ReactNode;
    label?: string;
    onClick?: () => void;
  }[];
  icon?: ReactNode;
  iconBorder?: boolean;
  onClick?: () => void;
  extraContent?: ReactNode;
}

function GPTCard({
  icon,
  iconBorder = true,
  title,
  desc,
  tags,
  children,
  disabled,
  operations,
  className,
  extraContent,
  ...props
}: PropsWithChildren<HtmlHTMLAttributes<HTMLDivElement> & Props>) {
  const iconNode = useMemo(() => {
    if (!icon) return null;

    if (typeof icon === 'string') {
      return (
        <Image
          className={classNames('w-11 h-11 rounded-full mr-4 object-contain bg-white', {
            'border border-gray-200': iconBorder,
          })}
          width={48}
          height={48}
          src={icon}
          alt={title}
        />
      );
    }

    return icon;
  }, [icon]);

  // TODO: 算子资源标签
  const tagNode = useMemo(() => {
    if (!tags || !tags.length) return null;
    return (
      <div className='flex items-center mt-1 flex-wrap'>
        {tags.map((tag, index) => {
          if (typeof tag === 'string') {
            return (
              <Tag key={index} className='text-xs' bordered={false} color='default'>
                {tag}
              </Tag>
            );
          }
          return (
            <Tag key={index} className='text-xs' bordered={tag.border ?? false} color={tag.color}>
              {tag.text}
            </Tag>
          );
        })}
      </div>
    );
  }, [tags]);

  return (
    <div
      className={classNames(
        'group/card relative flex flex-col w-72 rounded justify-between text-black bg-white shadow-[0_8px_16px_-10px_rgba(100,100,100,.08)] hover:shadow-[0_14px_20px_-10px_rgba(100,100,100,.15)] dark:bg-[#232734] dark:text-white dark:hover:border-white transition-[transfrom_shadow] duration-300 hover:-translate-y-1 min-h-fit',
        {
          'grayscale cursor-no-drop': disabled,
          'cursor-pointer': !disabled && !!props.onClick,
        },
        className,
      )}
      {...props}
    >
      <div className='p-4 0'>
        <div className='flex items-center'>
          {iconNode}
          <div className='flex flex-col'>
            <Popover title={title}>
              <h2 className='text-sm font-semibold line-clamp-1 pr-8'>{title}</h2>
            </Popover>

            {tagNode}
          </div>
        </div>
        {desc && (
          <Tooltip title={desc}>
            <p className='mt-2 text-sm text-gray-500 font-normal line-clamp-2'>{desc}</p>
          </Tooltip>
        )}
      </div>
      <div>
        {children}
        {operations && !!operations.length && (
          <div className='flex flex-wrap items-center justify-center border-t border-solid border-gray-100 dark:border-theme-dark'>
            {operations.map((item, index) => (
              <Tooltip key={`operation-${index}`} title={item.label}>
                <div
                  className='relative flex flex-1 items-center justify-center h-11 text-gray-400 hover:text-blue-500 transition-colors duration-300 cursor-pointer'
                  onClick={e => {
                    e.stopPropagation();
                    item.onClick?.();
                  }}
                >
                  {item.children}
                  {index < operations.length - 1 && (
                    <div className='w-[1px] h-6 absolute top-2 right-0 bg-gray-100 rounded dark:bg-theme-dark' />
                  )}
                </div>
              </Tooltip>
            ))}
          </div>
        )}
      </div>
      <div className='absolute top-2 right-4 '>{extraContent}</div>
    </div>
  );
}

export default memo(GPTCard);
