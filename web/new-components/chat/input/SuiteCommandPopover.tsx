import type { SuiteCommand, SuiteItem } from '@/types/suite';
import { getSuiteCommandGroups, type SuiteCommandOption } from '@/utils/suite-commands';
import classNames from 'classnames';
import React, {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from 'react';

export interface SuiteCommandPopoverHandle {
  /** Call before the composer's send handler. True means the menu consumed the key. */
  handleKeyDown: (event: React.KeyboardEvent) => boolean;
}

export interface SuiteCommandPopoverProps {
  visible: boolean;
  suites: SuiteItem[];
  /** Filter text after the slash; a leading slash is also accepted. */
  query: string;
  onSelect: (suite: SuiteItem, command: SuiteCommand) => void;
  onClose: () => void;
  locale?: string;
  id?: string;
  className?: string;
  /** Keep clicks in the composer from being treated as clicks outside the menu. */
  anchorRef?: React.RefObject<HTMLElement | null>;
  /** Bind this value to the focused text area's aria-activedescendant. */
  onActiveDescendantChange?: (id: string | undefined) => void;
}

const SuiteCommandPopover = forwardRef<SuiteCommandPopoverHandle, SuiteCommandPopoverProps>(
  (
    { visible, suites, query, onSelect, onClose, locale = 'zh', id, className, anchorRef, onActiveDescendantChange },
    ref,
  ) => {
    const generatedId = useId();
    const listboxId = id || `suite-commands-${generatedId}`;
    const containerRef = useRef<HTMLDivElement>(null);
    const [activeKey, setActiveKey] = useState<string | null>(null);
    const groups = useMemo(() => getSuiteCommandGroups(suites, query, locale), [suites, query, locale]);
    const options = useMemo(() => groups.flatMap(group => group.options), [groups]);
    const activeOption = options.find(option => option.key === activeKey) || options[0];
    const activeId = visible && activeOption ? `${listboxId}-${activeOption.key}` : undefined;
    const isEnglish = locale.toLowerCase().startsWith('en');

    useEffect(() => setActiveKey(null), [visible, query]);

    useEffect(() => {
      onActiveDescendantChange?.(activeId);
    }, [activeId, onActiveDescendantChange]);

    useEffect(() => () => onActiveDescendantChange?.(undefined), [onActiveDescendantChange]);

    useEffect(() => {
      if (!visible || !activeId) return;
      document.getElementById(activeId)?.scrollIntoView?.({ block: 'nearest' });
    }, [visible, activeId]);

    useEffect(() => {
      if (!visible) return;
      const handleClickOutside = (event: MouseEvent) => {
        const target = event.target as Node;
        if (!containerRef.current?.contains(target) && !anchorRef?.current?.contains(target)) onClose();
      };
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [visible, onClose, anchorRef]);

    const selectOption = useCallback(
      (option: SuiteCommandOption) => {
        onSelect(option.suite, option.command);
        onClose();
      },
      [onSelect, onClose],
    );

    const handleKeyDown = useCallback(
      (event: React.KeyboardEvent): boolean => {
        if (!visible || event.nativeEvent.isComposing || event.keyCode === 229) return false;
        if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return false;
        if (!['ArrowDown', 'ArrowUp', 'Enter', 'Escape'].includes(event.key)) return false;
        event.preventDefault();
        event.stopPropagation();
        if (event.key === 'Escape') {
          onClose();
        } else if (event.key === 'Enter') {
          // A slash query with no matches must not accidentally submit a chat turn.
          if (activeOption) selectOption(activeOption);
        } else if (options.length) {
          const currentIndex = options.findIndex(option => option.key === activeOption?.key);
          const delta = event.key === 'ArrowDown' ? 1 : -1;
          setActiveKey(options[(currentIndex + delta + options.length) % options.length].key);
        }
        return true;
      },
      [visible, activeOption, options, onClose, selectOption],
    );

    useImperativeHandle(ref, () => ({ handleKeyDown }), [handleKeyDown]);

    if (!visible) return null;

    return (
      <div
        ref={containerRef}
        className={classNames(
          'absolute bottom-full left-0 z-50 mb-2 w-full max-w-[520px] overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-[#1e1f24]',
          className,
        )}
        onKeyDown={handleKeyDown}
      >
        <div className='border-b border-gray-100 px-4 py-2.5 text-xs font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400'>
          {isEnglish ? 'Expert suite commands' : '专家套件命令'}
        </div>
        <div
          id={listboxId}
          role='listbox'
          aria-label={isEnglish ? 'Expert suite commands' : '专家套件命令'}
          className='max-h-[320px] overflow-y-auto overscroll-contain p-1.5'
        >
          {groups.length ? (
            groups.map(group => (
              <div key={group.suite.name} role='group' aria-label={group.label}>
                <div className='px-2.5 pb-1 pt-2 text-xs font-medium text-gray-500 dark:text-gray-400'>
                  {group.label}
                </div>
                {group.options.map(option => (
                  <button
                    key={option.key}
                    id={`${listboxId}-${option.key}`}
                    type='button'
                    role='option'
                    aria-selected={option.key === activeOption?.key}
                    tabIndex={-1}
                    className={classNames(
                      'flex w-full flex-col gap-1 rounded-xl px-2.5 py-2 text-left transition-colors',
                      option.key === activeOption?.key
                        ? 'bg-green-50 dark:bg-green-900/20'
                        : 'hover:bg-gray-50 dark:hover:bg-gray-800',
                    )}
                    onMouseDown={event => event.preventDefault()}
                    onMouseEnter={() => setActiveKey(option.key)}
                    onClick={() => selectOption(option)}
                  >
                    <span className='flex w-full items-center gap-2'>
                      <span className='break-words font-mono text-sm text-green-700 dark:text-green-300'>
                        {option.label}
                      </span>
                      {option.label !== option.command.name && (
                        <span className='text-xs text-gray-500 dark:text-gray-400'>{option.command.name}</span>
                      )}
                    </span>
                    {option.description && (
                      <span className='text-xs leading-5 text-gray-500 dark:text-gray-400'>{option.description}</span>
                    )}
                  </button>
                ))}
              </div>
            ))
          ) : (
            <div role='status' className='px-3 py-5 text-center text-sm text-gray-500 dark:text-gray-400'>
              {query.trim()
                ? isEnglish
                  ? 'No matching commands'
                  : '没有匹配的命令'
                : isEnglish
                  ? 'No commands from enabled expert suites'
                  : '暂无已启用的专家套件命令'}
            </div>
          )}
        </div>
        <div className='border-t border-gray-100 px-4 py-2 text-xs text-gray-400 dark:border-gray-700 dark:text-gray-500'>
          {isEnglish ? '↑ ↓ Navigate · Enter Select · Esc Close' : '↑ ↓ 切换 · Enter 选择 · Esc 关闭'}
        </div>
      </div>
    );
  },
);

SuiteCommandPopover.displayName = 'SuiteCommandPopover';

export default SuiteCommandPopover;
