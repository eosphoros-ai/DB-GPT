import { DownOutlined } from '@ant-design/icons';
import classNames from 'classnames';
import React, { ReactNode, createContext, useCallback, useContext, useState } from 'react';

interface CollapsibleContextValue {
  open: boolean;
  toggle: () => void;
  onOpenChange?: (open: boolean) => void;
}

const CollapsibleContext = createContext<CollapsibleContextValue | null>(null);

function useCollapsible() {
  const context = useContext(CollapsibleContext);
  if (!context) {
    throw new Error('Collapsible components must be used within a Collapsible');
  }
  return context;
}

interface CollapsibleRootProps {
  children: ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  className?: string;
}

function CollapsibleRoot({
  children,
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  className,
}: CollapsibleRootProps) {
  const [internalOpen, setInternalOpen] = useState(defaultOpen);
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;

  const toggle = useCallback(() => {
    const newOpen = !open;
    if (!isControlled) {
      setInternalOpen(newOpen);
    }
    onOpenChange?.(newOpen);
  }, [open, isControlled, onOpenChange]);

  return (
    <CollapsibleContext.Provider value={{ open, toggle, onOpenChange }}>
      <div
        data-component='collapsible'
        data-state={open ? 'open' : 'closed'}
        className={classNames('oc-collapsible', className)}
      >
        {children}
      </div>
    </CollapsibleContext.Provider>
  );
}

interface CollapsibleTriggerProps {
  children: ReactNode;
  className?: string;
  asChild?: boolean;
}

function CollapsibleTrigger({ children, className, asChild }: CollapsibleTriggerProps) {
  const { toggle, open } = useCollapsible();

  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault();
    toggle();
  };

  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<any>, {
      onClick: handleClick,
      'data-state': open ? 'open' : 'closed',
      'aria-expanded': open,
    });
  }

  return (
    <button
      type='button'
      data-slot='collapsible-trigger'
      data-state={open ? 'open' : 'closed'}
      aria-expanded={open}
      className={classNames(
        'oc-collapsible-trigger',
        'w-full text-left cursor-pointer',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500/50',
        className,
      )}
      onClick={handleClick}
    >
      {children}
    </button>
  );
}

interface CollapsibleContentProps {
  children: ReactNode;
  className?: string;
  forceMount?: boolean;
}

function CollapsibleContent({ children, className, forceMount }: CollapsibleContentProps) {
  const { open } = useCollapsible();

  if (!open && !forceMount) {
    return null;
  }

  return (
    <div
      data-slot='collapsible-content'
      data-state={open ? 'open' : 'closed'}
      className={classNames(
        'oc-collapsible-content',
        'overflow-hidden',
        {
          'animate-collapsible-down': open,
          'animate-collapsible-up hidden': !open && forceMount,
        },
        className,
      )}
    >
      {children}
    </div>
  );
}

interface CollapsibleArrowProps {
  className?: string;
}

function CollapsibleArrow({ className }: CollapsibleArrowProps) {
  const { open } = useCollapsible();

  return (
    <span
      data-slot='collapsible-arrow'
      data-state={open ? 'open' : 'closed'}
      className={classNames(
        'oc-collapsible-arrow',
        'inline-flex items-center justify-center',
        'transition-transform duration-200',
        {
          'rotate-180': open,
        },
        className,
      )}
    >
      <DownOutlined className='text-xs text-gray-400' />
    </span>
  );
}

export const Collapsible = Object.assign(CollapsibleRoot, {
  Trigger: CollapsibleTrigger,
  Content: CollapsibleContent,
  Arrow: CollapsibleArrow,
});

export default Collapsible;
