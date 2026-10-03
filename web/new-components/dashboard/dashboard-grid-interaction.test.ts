import { bottom, cloneLayout, moveElement, type Layout } from 'react-grid-layout/core';
import { describe, expect, it } from 'vitest';
import { dashboardGridCompactor } from './dashboard-grid-interaction';

const initial: Layout = [
  { i: 'top', x: 0, y: 0, w: 6, h: 4 },
  { i: 'neighbour', x: 6, y: 0, w: 6, h: 4 },
  { i: 'middle', x: 0, y: 4, w: 12, h: 7 },
  { i: 'bottom', x: 0, y: 11, w: 6, h: 7 },
];
const positions = (layout: Layout) => layout.map(({ i, x, y, w, h }) => ({ i, x, y, w, h }));
const drag = (x: number, y: number) => {
  const layout = cloneLayout(initial);
  return moveElement(layout, layout[0], x, y, true, dashboardGridCompactor.preventCollision, null, 12, false);
};

describe('dashboard grid interactions', () => {
  it('blocks an occupied drop without pushing any following cards or lengthening the dashboard', () => {
    const moved = drag(0, 4);
    expect(positions(moved)).toEqual(positions(initial));
    expect(bottom(moved)).toBe(bottom(initial));
  });

  it('moves one card into a free area without moving its neighbours', () => {
    const moved = drag(6, 11);
    expect(positions(moved).slice(1)).toEqual(positions(initial).slice(1));
    expect(moved[0]).toMatchObject({ x: 6, y: 11 });
    expect(bottom(moved)).toBe(bottom(initial));
  });

  it('preserves intentional spaces during rendering and after a drop', () => {
    const moved = drag(6, 11);
    expect(positions(dashboardGridCompactor.compact(moved, 12))).toEqual(positions(moved));
  });
});
