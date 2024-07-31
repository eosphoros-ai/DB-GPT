import { Advice, AdvisorConfig, ChartId, Datum, FieldInfo, PureChartKnowledge } from '@antv/ava';

export type ChartType = ChartId | string;

export type Specification = Advice['spec'] | any;
export type RuleConfig = AdvisorConfig['ruleCfg'];

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
