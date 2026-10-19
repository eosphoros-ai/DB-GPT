import countries from './geo/world-countries.json';

export interface ChartDatum {
  label: string;
  value: number;
  source: Record<string, unknown>;
}
export function numericChartData(data: Record<string, unknown>[], category: string, value: string): ChartDatum[] {
  return data.flatMap(source => {
    const raw = source[value];
    if (raw == null || raw === '' || typeof raw === 'boolean' || !Number.isFinite(Number(raw))) return [];
    return [{ label: String(source[category] ?? '未分类'), value: Number(raw), source }];
  });
}
export function waterfallSteps(data: ChartDatum[]) {
  let total = 0;
  return data.map(item => {
    const start = total;
    total += item.value;
    return { ...item, start, end: total };
  });
}
/** Old AI queries sometimes returned an already computed final total. Only
 * recognize a declared terminal total after independently reconciling its value.
 * Ordinary categories and unbalanced values are never silently removed. */
export function waterfallSeries(data: ChartDatum[]) {
  const last = data.at(-1);
  const preceding = data.slice(0, -1).reduce((sum, item) => sum + item.value, 0);
  const declared =
    last &&
    (last.source.is_total === true ||
      last.source.is_total === 1 ||
      /^(合计|总计|总额|total|grand total)$/i.test(last.label.trim()));
  const reconciled = last && Math.abs(last.value - preceding) <= Math.max(1e-8, Math.abs(preceding) * 1e-9);
  const deltas = data.length > 1 && declared && reconciled ? data.slice(0, -1) : data;
  const steps = waterfallSteps(deltas).map(item => ({ ...item, isTotal: false }));
  const total = steps.at(-1)?.end ?? 0;
  return [...steps, { label: '合计', value: total, start: 0, end: total, source: {}, isTotal: true }];
}
export function treemapBoxes(
  data: ChartDatum[],
  x = 0,
  y = 0,
  width = 560,
  height = 320,
): Array<ChartDatum & { x: number; y: number; width: number; height: number }> {
  if (!data.length) return [];
  if (data.length === 1) return [{ ...data[0], x, y, width, height }];
  const total = data.reduce((sum, item) => sum + item.value, 0);
  if (total <= 0) return [];
  let split = 1,
    subtotal = data[0].value;
  while (split < data.length - 1 && subtotal < total / 2) subtotal += data[split++].value;
  const ratio = subtotal / total;
  return width >= height
    ? [
        ...treemapBoxes(data.slice(0, split), x, y, width * ratio, height),
        ...treemapBoxes(data.slice(split), x + width * ratio, y, width * (1 - ratio), height),
      ]
    : [
        ...treemapBoxes(data.slice(0, split), x, y, width, height * ratio),
        ...treemapBoxes(data.slice(split), x, y + height * ratio, width, height * (1 - ratio)),
      ];
}
const aliases = new Map(
  countries.flatMap(country => country.aliases.map(alias => [alias.toLocaleLowerCase(), country] as const)),
);
aliases.set('uk', countries.find(country => country.id === 'GBR')!);
aliases.set('usa', countries.find(country => country.id === 'USA')!);
export function mapCountryData(data: ChartDatum[]) {
  const matched = new Map<string, ChartDatum & { country: (typeof countries)[number] }>();
  const unmatched: ChartDatum[] = [];
  for (const item of data) {
    const country = aliases.get(item.label.trim().toLocaleLowerCase());
    if (!country) {
      unmatched.push(item);
      continue;
    }
    const previous = matched.get(country.id);
    matched.set(country.id, { ...item, value: item.value + (previous?.value || 0), country });
  }
  return { matched: [...matched.values()], unmatched };
}
export { countries };
