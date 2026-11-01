import { DashboardFieldType, DashboardFilterOption, DashboardSchemaV1, DashboardSnapshot } from '@/types/dashboard';

export interface DashboardFilterFieldCandidate {
  field: string;
  label: string;
  widgetIds: string[];
  options: DashboardFilterOption[];
  dataTypes: DashboardFieldType[];
  dateRange?: [string, string];
  rangeIsPartial: boolean;
}

const isFilterValue = (value: unknown): value is string | number | boolean =>
  typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean';

const optionKey = (value: string | number | boolean) => `${typeof value}:${String(value)}`;

const normalizedDateValue = (value: unknown) => {
  if (typeof value !== 'string') return null;
  const match = value.trim().match(/^(\d{4}-\d{2}-\d{2})/);
  if (!match) return null;
  const parsed = Date.parse(`${match[1]}T00:00:00Z`);
  return Number.isNaN(parsed) ? null : match[1];
};

export const buildDashboardFilterFieldCandidates = (
  schema: DashboardSchemaV1,
  snapshot?: DashboardSnapshot | null,
): DashboardFilterFieldCandidate[] => {
  const candidates = new Map<
    string,
    {
      field: string;
      widgetTitles: string[];
      widgetIds: string[];
      values: Map<string, string | number | boolean>;
      dataTypes: Set<DashboardFieldType>;
      minDate?: string;
      maxDate?: string;
      rangeIsPartial: boolean;
    }
  >();

  schema.widgets.forEach(widget => {
    const result = snapshot?.widgets[widget.id];
    const resultColumns = result?.columns || [];
    const declaredFields = widget.query.output_fields.map(field => field.name);
    const fields = Array.from(new Set([...declaredFields, ...resultColumns]));

    fields.forEach(field => {
      const normalized = field.toLocaleLowerCase();
      const current = candidates.get(normalized) || {
        field,
        widgetTitles: [],
        widgetIds: [],
        values: new Map<string, string | number | boolean>(),
        dataTypes: new Set<DashboardFieldType>(),
        rangeIsPartial: false,
      };
      if (!current.widgetIds.includes(widget.id)) current.widgetIds.push(widget.id);
      if (!current.widgetTitles.includes(widget.title)) current.widgetTitles.push(widget.title);

      const declaredType = widget.query.output_fields.find(
        outputField => outputField.name.toLocaleLowerCase() === normalized,
      )?.type;
      if (declaredType) current.dataTypes.add(declaredType);

      const columnIndex = resultColumns.findIndex(column => column.toLocaleLowerCase() === normalized);
      if (columnIndex >= 0) {
        current.rangeIsPartial = current.rangeIsPartial || Boolean(result?.truncated);
        (result?.rows || []).forEach(row => {
          const value = row[columnIndex];
          if (isFilterValue(value) && current.values.size < 200) current.values.set(optionKey(value), value);
          const dateValue = normalizedDateValue(value);
          if (dateValue) {
            current.minDate = current.minDate && current.minDate < dateValue ? current.minDate : dateValue;
            current.maxDate = current.maxDate && current.maxDate > dateValue ? current.maxDate : dateValue;
          }
        });
      }
      candidates.set(normalized, current);
    });
  });

  return Array.from(candidates.values()).map(candidate => ({
    field: candidate.field,
    label: `${candidate.field} · ${candidate.widgetTitles.slice(0, 2).join(' / ')}`,
    widgetIds: candidate.widgetIds,
    options: Array.from(candidate.values.values()).map(value => ({ label: String(value), value })),
    dataTypes: Array.from(candidate.dataTypes),
    dateRange: candidate.minDate && candidate.maxDate ? [candidate.minDate, candidate.maxDate] : undefined,
    rangeIsPartial: candidate.rangeIsPartial,
  }));
};

export const normalizeDashboardFilterParameter = (value: string, fallback = 'filter_value') => {
  const normalized = value
    .trim()
    .replace(/[^a-zA-Z0-9_]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .replace(/^[0-9]+/, '');
  return normalized || fallback;
};

export const sqlUsesNamedParameter = (sql: string, parameter: string) => {
  const normalized = normalizeDashboardFilterParameter(parameter);
  const escaped = normalized.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(^|[^:a-zA-Z0-9_]):${escaped}(?![a-zA-Z0-9_])`).test(sql);
};

export const buildDashboardFilterParameterCandidates = (schema: DashboardSchemaV1) => {
  const parameters = new Set<string>();
  const collect = (sql: string) => {
    for (const match of sql.matchAll(/:[a-zA-Z_][a-zA-Z0-9_]*/g)) {
      const index = match.index ?? 0;
      if (index > 0 && sql[index - 1] === ':') continue;
      parameters.add(match[0].slice(1));
    }
  };

  schema.widgets.forEach(widget => {
    collect(widget.query.sql || '');
    widget.query.federation?.sources.forEach(source => collect(source.sql || ''));
  });
  return Array.from(parameters).sort((left, right) => left.localeCompare(right));
};

export const recommendDashboardFilterParameter = (filterId: string, field: string, candidates: string[]) => {
  const normalizedField = normalizeDashboardFilterParameter(field).toLocaleLowerCase();
  const normalizedId = normalizeDashboardFilterParameter(filterId).toLocaleLowerCase();
  const roots = [normalizedField, normalizedId]
    .flatMap(value => [value, value.replace(/_?(ids?|values?)$/i, '')])
    .filter(Boolean);
  const scored = candidates
    .map(candidate => {
      const normalized = candidate.toLocaleLowerCase();
      let score = 0;
      roots.forEach(root => {
        if (normalized === root) score = Math.max(score, 100);
        if (normalized === `${root}_ids`) score = Math.max(score, 95);
        if (normalized === `${root}_id`) score = Math.max(score, 90);
        if (normalized.startsWith(`${root}_`) || normalized.endsWith(`_${root}`)) score = Math.max(score, 75);
        if (normalized.includes(root)) score = Math.max(score, 50);
      });
      return { candidate, score };
    })
    .sort((left, right) => right.score - left.score || left.candidate.localeCompare(right.candidate));
  return scored[0]?.score ? scored[0].candidate : null;
};

export interface DashboardDateParameterRecommendation {
  startParameter: string;
  endParameter: string;
}

export const recommendDashboardDateFilterParameters = (
  filterId: string,
  field: string,
  candidates: string[],
): DashboardDateParameterRecommendation | null => {
  const roots = [normalizeDashboardFilterParameter(field), normalizeDashboardFilterParameter(filterId)]
    .flatMap(value => [value.toLocaleLowerCase(), value.toLocaleLowerCase().replace(/_?(range|filter)$/i, '')])
    .filter(Boolean);
  const score = (candidate: string, boundary: 'start' | 'end') => {
    const normalized = candidate.toLocaleLowerCase();
    const boundaryTokens = boundary === 'start' ? ['start', 'from', 'begin', 'min'] : ['end', 'to', 'until', 'max'];
    let result = 0;
    roots.forEach(root => {
      boundaryTokens.forEach(token => {
        if (normalized === `${token}_${root}` || normalized === `${root}_${token}`) result = Math.max(result, 120);
        if (normalized.includes(root) && normalized.includes(token)) result = Math.max(result, 100);
      });
    });
    boundaryTokens.forEach(token => {
      if (normalized.startsWith(`${token}_`) || normalized.endsWith(`_${token}`)) result = Math.max(result, 40);
    });
    return result;
  };
  const pick = (boundary: 'start' | 'end', excluded?: string) =>
    candidates
      .filter(candidate => candidate !== excluded)
      .map(candidate => ({ candidate, score: score(candidate, boundary) }))
      .sort((left, right) => right.score - left.score || left.candidate.localeCompare(right.candidate))[0];

  const start = pick('start');
  const end = pick('end', start?.candidate);
  if (!start?.score || !end?.score) return null;
  return { startParameter: start.candidate, endParameter: end.candidate };
};
