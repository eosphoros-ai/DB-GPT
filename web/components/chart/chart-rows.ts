const rowSizesByCount = [[], [1], [2], [1, 2], [1, 3], [2, 1, 2], [2, 1, 3], [3, 1, 3], [3, 2, 3]];

export function groupChartsIntoRows<T>(charts: T[]): T[][] {
  const sizes = rowSizesByCount[charts.length];
  const rows: T[][] = [];
  for (let start = 0; start < charts.length; ) {
    const size = sizes?.[rows.length] ?? 3;
    rows.push(charts.slice(start, start + size));
    start += size;
  }
  return rows;
}
