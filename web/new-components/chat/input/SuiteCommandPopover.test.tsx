import type { SuiteCommand, SuiteItem } from '@/types/suite';
import { getSuiteCommandQuery } from '@/utils/suite-commands';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useRef, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import SuiteCommandPopover, { type SuiteCommandPopoverHandle } from './SuiteCommandPopover';

afterEach(cleanup);

const financial: SuiteItem = {
  id: 1,
  name: 'financial-report',
  display: '财报分析',
  status: 'enabled',
  version: '1.0.0',
  source: 'official',
  manifest_snapshot: {
    display_en: 'Financial Reports',
    commands: [
      { name: '/分析', display_en: '/analyze', description: '上传财报 PDF，分析现金流', aliases: ['/annual'] },
    ],
  },
};
const database: SuiteItem = {
  ...financial,
  id: 2,
  name: 'db-analysis',
  display: '智能分析',
  manifest_snapshot: { commands: [{ name: '/分析', description: '分析数据库中的业务指标' }] },
};
const suites = [financial, database, { ...financial, name: 'disabled', display: '禁用套件', status: 'disabled' }];

function Composer({
  availableSuites = suites,
  onSelect = vi.fn(),
  onSend = vi.fn(),
  locale = 'zh',
}: {
  availableSuites?: SuiteItem[];
  onSelect?: (suite: SuiteItem, command: SuiteCommand) => void;
  onSend?: () => void;
  locale?: string;
}) {
  const [value, setValue] = useState('/');
  const [open, setOpen] = useState(true);
  const [activeId, setActiveId] = useState<string>();
  const menu = useRef<SuiteCommandPopoverHandle>(null);
  const anchor = useRef<HTMLDivElement>(null);
  const query = getSuiteCommandQuery(value);
  return (
    <div ref={anchor}>
      <textarea
        aria-label='Message'
        aria-controls='suite-menu'
        aria-expanded={open && query !== null}
        aria-activedescendant={activeId}
        value={value}
        onChange={event => {
          setValue(event.target.value);
          setOpen(true);
        }}
        onKeyDown={event => {
          if (event.nativeEvent.isComposing || event.keyCode === 229) return;
          if (menu.current?.handleKeyDown(event)) return;
          if (event.key === 'Enter' && !event.shiftKey) onSend();
        }}
      />
      <SuiteCommandPopover
        ref={menu}
        id='suite-menu'
        visible={open && query !== null}
        suites={availableSuites}
        query={query || ''}
        locale={locale}
        onSelect={onSelect}
        onClose={() => setOpen(false)}
        anchorRef={anchor}
        onActiveDescendantChange={setActiveId}
      />
    </div>
  );
}

describe('SuiteCommandPopover', () => {
  it('groups enabled commands and exposes the active option to the composer', () => {
    render(<Composer />);
    expect(screen.getByRole('listbox', { name: '专家套件命令' })).toBeTruthy();
    expect(screen.getAllByRole('group').map(group => group.getAttribute('aria-label'))).toEqual([
      '财报分析',
      '智能分析',
    ]);
    expect(screen.queryByText('禁用套件')).toBeNull();
    const active = screen.getByRole('option', { selected: true });
    expect(active.textContent).toContain('分析现金流');
    expect(screen.getByRole('textbox').getAttribute('aria-activedescendant')).toBe(active.id);
  });

  it('navigates across suites, wraps, and selects the command with its own suite without sending', () => {
    const onSelect = vi.fn();
    const onSend = vi.fn();
    render(<Composer onSelect={onSelect} onSend={onSend} />);
    const input = screen.getByRole('textbox');
    fireEvent.keyDown(input, { key: 'ArrowUp' });
    expect(screen.getByRole('option', { selected: true }).textContent).toContain('业务指标');
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    expect(screen.getByRole('option', { selected: true }).textContent).toContain('现金流');
    fireEvent.keyDown(input, { key: 'ArrowDown' });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith(database, database.manifest_snapshot?.commands?.[0]);
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.queryByRole('listbox')).toBeNull();
    expect(input.getAttribute('aria-activedescendant')).toBeNull();
  });

  it('filters by purpose or alias and lets a click select without moving focus from the input', () => {
    const onSelect = vi.fn();
    render(<Composer onSelect={onSelect} />);
    const input = screen.getByRole('textbox');
    input.focus();
    fireEvent.change(input, { target: { value: '/annual' } });
    expect(screen.getAllByRole('option')).toHaveLength(1);
    const option = screen.getByRole('option');
    fireEvent.mouseDown(option);
    expect(document.activeElement).toBe(input);
    fireEvent.click(option);
    expect(onSelect).toHaveBeenCalledWith(financial, financial.manifest_snapshot?.commands?.[0]);
  });

  it('shows a filtered empty state and consumes Enter instead of submitting the slash query', () => {
    const onSend = vi.fn();
    const onSelect = vi.fn();
    render(<Composer onSend={onSend} onSelect={onSelect} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: '/无匹配' } });
    expect(screen.getByRole('status').textContent).toBe('没有匹配的命令');
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    expect(onSend).not.toHaveBeenCalled();
    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getByRole('textbox').getAttribute('aria-activedescendant')).toBeNull();
  });

  it('closes with Escape and outside clicks while preserving the typed query', () => {
    render(<Composer />);
    const input = screen.getByRole('textbox');
    fireEvent.mouseDown(input);
    expect(screen.getByRole('listbox')).toBeTruthy();
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByRole('listbox')).toBeNull();
    expect((input as HTMLTextAreaElement).value).toBe('/');
    fireEvent.change(input, { target: { value: '/annual' } });
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('does not select or send while the user confirms Chinese input', () => {
    const onSelect = vi.fn();
    const onSend = vi.fn();
    render(<Composer onSelect={onSelect} onSend={onSend} />);
    const input = screen.getByRole('textbox');
    fireEvent.keyDown(input, { key: 'Enter', isComposing: true });
    fireEvent.keyDown(input, { key: 'Enter', keyCode: 229 });
    expect(onSelect).not.toHaveBeenCalled();
    expect(onSend).not.toHaveBeenCalled();
    expect(screen.getByRole('listbox')).toBeTruthy();
  });

  it('drops an active command when its suite becomes disabled', () => {
    const onSelect = vi.fn();
    const { rerender } = render(<Composer onSelect={onSelect} />);
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'ArrowDown' });
    rerender(<Composer availableSuites={[financial, { ...database, status: 'disabled' }]} onSelect={onSelect} />);
    fireEvent.keyDown(screen.getByRole('textbox'), { key: 'Enter' });
    expect(onSelect).toHaveBeenCalledWith(financial, financial.manifest_snapshot?.commands?.[0]);
  });

  it('localizes the menu and distinguishes no enabled commands from no search matches', () => {
    const { rerender } = render(<Composer locale='en-US' />);
    expect(screen.getByRole('listbox', { name: 'Expert suite commands' })).toBeTruthy();
    expect(screen.getByText('/analyze')).toBeTruthy();
    rerender(<Composer locale='en-US' availableSuites={[]} />);
    expect(screen.getByRole('status').textContent).toBe('No commands from enabled expert suites');
  });
});
