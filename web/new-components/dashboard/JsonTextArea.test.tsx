import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import JsonTextArea from './JsonTextArea';

describe('JsonTextArea', () => {
  it('commits parsed JSON only after the editor loses focus', () => {
    const onCommit = vi.fn();
    render(<JsonTextArea label='Style JSON' value={{ color: 'blue' }} onCommit={onCommit} />);

    const editor = screen.getByRole('textbox', { name: 'Style JSON' });
    fireEvent.change(editor, { target: { value: '{"color":"red","precision":2}' } });
    expect(onCommit).not.toHaveBeenCalled();

    fireEvent.blur(editor);
    expect(onCommit).toHaveBeenCalledWith({ color: 'red', precision: 2 });
  });

  it('keeps the previous value and shows an error for invalid JSON', () => {
    const onCommit = vi.fn();
    render(<JsonTextArea label='Options JSON' value={[]} onCommit={onCommit} />);

    const editor = screen.getByRole('textbox', { name: 'Options JSON' });
    fireEvent.change(editor, { target: { value: '[{"label":"A"}' } });
    fireEvent.blur(editor);

    expect(onCommit).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toBeTruthy();
  });
});
