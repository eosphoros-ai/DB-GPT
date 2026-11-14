import cls from 'classnames';
import React from 'react';
import './style.css';

/**
 * Chrome-less layout for /construct/* pages.
 *
 * The horizontal tab bar that used to duplicate the sidebar navigation is
 * gone: the sidebar is the single entry point, so this layout only provides
 * the page surface (gradient background + a scrolling content region that
 * replaces the old Tabs content-holder).
 */
function ConstructLayout({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cls(
        'flex flex-col h-full w-full overflow-y-auto dark:bg-gradient-dark bg-gradient-light bg-cover bg-center',
        className,
      )}
    >
      {children}
    </div>
  );
}

export default ConstructLayout;
