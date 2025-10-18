import { Button, ButtonProps } from 'antd';
import { useRouter } from 'next/router';
import React, { useCallback } from 'react';

export const NavTo = ({
  href,
  type = 'link',
  className = '',
  openNewTab = false,
  children,
}: {
  href: string;
  type?: ButtonProps['type'];
  className?: string;
  openNewTab?: boolean;
  children: React.ReactNode;
}) => {
  const goToList = useCallback(() => {
    router.push(href);
  }, [href]);

  const router = useRouter();

  if (openNewTab) {
    return (
      <Button type={type} className={className}>
        <a href={href} target='_blank' rel='noopener noreferrer'>
          {children}
        </a>
      </Button>
    );
  }

  return (
    <Button type={type} className={className} onClick={goToList}>
      {children}
    </Button>
  );
};
