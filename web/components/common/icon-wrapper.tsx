import classNames from 'classnames';
import React from 'react';

interface IconWrapperProps {
  children: React.ReactNode;
  className?: string;
}

// Icon wrapper, with background color and hover color. same width and height
const IconWrapper: React.FC<IconWrapperProps> = ({ children, className }) => {
  return (
    <div
      className={classNames(
        'flex justify-center items-center w-8 h-8 rounded-full dark:bg-zinc-700 hover:bg-stone-200 dark:hover:bg-zinc-900',
        className,
      )}
    >
      {children}
    </div>
  );
};

export default IconWrapper;
