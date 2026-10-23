import type { CSSProperties } from 'react';

/**
 * Sidebar fold/unfold glyph aligned with the 千问办公 (AntWork) chrome:
 * a rounded panel outline carrying a filled rail on its left edge,
 * replacing the old "text-indent" MenuFold/MenuUnfold glyphs.
 */
function PanelLeft({
  style,
  className,
}: {
  style?: CSSProperties;
  className?: string;
}) {
  return (
    <svg
      width='1em'
      height='1em'
      viewBox='0 0 24 24'
      fill='none'
      className={className}
      style={style}
      aria-hidden='true'
    >
      <rect
        x='3.25'
        y='4.75'
        width='17.5'
        height='14.5'
        rx='3.25'
        stroke='currentColor'
        strokeWidth='1.7'
      />
      <rect x='6.9' y='8.4' width='2.9' height='7.2' rx='1.45' fill='currentColor' />
    </svg>
  );
}

export default PanelLeft;
