import { resolveDashboardTheme } from '../dashboard/dashboard-appearance';

type Bounds = { min: ArrayLike<number>; max: ArrayLike<number> };
type MeasuredNode = {
  getBounds: () => Bounds;
  getAnimations?: () => { effect?: { getKeyframes: () => Record<string, unknown>[] } }[];
  cloneNode?: (deep: boolean) => MeasuredNode;
  parentNode?: { appendChild: (node: MeasuredNode) => void };
  attr?: (attributes: Record<string, unknown>) => void;
  destroy?: () => void;
  style: { visibility?: string };
};
type LabelNode = MeasuredNode & {
  __data__?: { dependentElement?: MeasuredNode };
};

/** Collision decisions must use the final geometry, not an in-flight resize tween. */
export function settledDashboardBounds(node: MeasuredNode): Bounds {
  const keyframes = (node.getAnimations?.() || []).flatMap(animation => {
    const frames = animation.effect?.getKeyframes() || [];
    return frames.length ? [frames[frames.length - 1]] : [];
  });
  if (!keyframes.length || !node.cloneNode || !node.parentNode) return node.getBounds();
  const clone = node.cloneNode(true);
  try {
    for (const frame of keyframes) clone.attr?.(frame);
    clone.style.visibility = 'hidden';
    node.parentNode.appendChild(clone);
    const bounds = clone.getBounds();
    return { min: Array.from(bounds.min), max: Array.from(bounds.max) };
  } finally {
    clone.destroy?.();
  }
}

const intersects = (a: Bounds, b: Bounds, gap = 0) =>
  a.min[0] < b.max[0] + gap - 0.5 &&
  a.max[0] > b.min[0] - gap + 0.5 &&
  a.min[1] < b.max[1] + gap - 0.5 &&
  a.max[1] > b.min[1] - gap + 0.5;

/** G2 label transform: hide entire measured labels, never ellipsize or move into bars. */
export function hideUnfittingDashboardLabels(
  labels: LabelNode[],
  width: number,
  height: number,
  obstacles: Bounds[] = [],
) {
  const shown: Bounds[] = [];
  const bars = labels.flatMap(label =>
    label.__data__?.dependentElement ? [settledDashboardBounds(label.__data__.dependentElement)] : [],
  );
  for (const label of labels) {
    label.style.visibility = 'visible';
    const box = settledDashboardBounds(label);
    const fits = box.min[0] >= 0 && box.min[1] >= 0 && box.max[0] <= width && box.max[1] <= height;
    const blocked = [...bars, ...obstacles].some(other => intersects(box, other));
    if (!fits || blocked || shown.some(other => intersects(box, other, 4))) label.style.visibility = 'hidden';
    else shown.push(box);
  }
  return labels;
}

export const dashboardBarLabelTransform = () => (labels: LabelNode[], context: any) => {
  const root = context.canvas.document.documentElement;
  const obstacles = root
    .querySelectorAll('text')
    .filter((node: any) => /axis-label|legend.*label/.test(node.className) && node.isVisible())
    .map((node: MeasuredNode) => settledDashboardBounds(node));
  obstacles.push(
    ...root
      .querySelectorAll('.element')
      .filter((node: any) => (node.attr('markType') || node.markType) === 'interval')
      .map((node: MeasuredNode) => settledDashboardBounds(node)),
  );
  const { width, height } = context.canvas.getConfig();
  return hideUnfittingDashboardLabels(labels, width, height, obstacles);
};

export const dashboardBarLabel = (config: {
  yField?: string;
  chartType: string;
  visualTheme?: { text: string };
  measureFormat?: { format: (value: unknown) => string };
}) => {
  const horizontal = config.chartType === 'bar';
  const negative = (datum: Record<string, unknown>) => Number(datum[config.yField || 'y']) < 0;
  return {
    text: (datum: Record<string, unknown>) =>
      config.measureFormat?.format(datum[config.yField || 'y']) ?? String(datum[config.yField || 'y'] ?? '—'),
    position: (datum: Record<string, unknown>) =>
      horizontal ? (negative(datum) ? 'left' : 'right') : negative(datum) ? 'bottom' : 'top',
    textBaseline: (datum: Record<string, unknown>) => (horizontal ? 'middle' : negative(datum) ? 'top' : 'bottom'),
    textAlign: (datum: Record<string, unknown>) => (horizontal ? (negative(datum) ? 'end' : 'start') : 'center'),
    dx: (datum: Record<string, unknown>) => (horizontal ? (negative(datum) ? -4 : 4) : 0),
    dy: (datum: Record<string, unknown>) => (horizontal ? 0 : negative(datum) ? 4 : -4),
    fill: config.visualTheme?.text || resolveDashboardTheme(undefined).text,
    fontSize: 11,
    wordWrap: false,
    transform: [{ type: dashboardBarLabelTransform }],
  };
};
