import { Advice, AdvisorConfig, ChartId, Datum, FieldInfo, PureChartKnowledge } from '@antv/ava';

export type ChartType = ChartId | string;

export type Specification = Advice['spec'] | any;
export type RuleConfig = AdvisorConfig['ruleCfg'];

export type ChartRenderObservation = {
  renderer: 'g2' | 'table';
  state: 'rendered' | 'failed' | 'not_rendered';
  duration_ms?: number;
  options?: Record<string, unknown>;
  error?: string;
};

export type AutoChartProps = {
  data: Datum[];
  /** Chart type which are suggestted. */
  chartType: ChartType[];
  /** Charts exclude or include. */
  scopeOfCharts?: {
    exclude?: string[];
    include?: string[];
  };
  /** Customize rules. */
  ruleConfig?: RuleConfig;
  /** Hide chat-only recommendation, chart switching and download controls. */
  showControls?: boolean;
  onRenderObservation?: (observation: ChartRenderObservation) => void;
};

export type ChartKnowledge = PureChartKnowledge & { toSpec?: any };

export type CustomChart = {
  /** Chart type ID, unique. */
  chartType: ChartType;
  /** Chart knowledge. */
  chartKnowledge: ChartKnowledge;
  /** Chart name. */
  chineseName?: string;
};

export type GetChartConfigProps = {
  data: Datum[];
  spec: Specification;
  dataProps: FieldInfo[];
  chartType?: ChartType;
};

export type CustomAdvisorConfig = {
  charts?: CustomChart[];
  scopeOfCharts?: {
    exclude?: string[];
    include?: string[];
  };
  ruleConfig?: RuleConfig;
};
