import { Advisor, CkbConfig } from '@antv/ava';
import type { Advice, AdviseParams, AdvisorConfig, ChartKnowledgeBase } from '@antv/ava';
import type { CustomAdvisorConfig, RuleConfig, Specification } from '../types';

export type CustomRecommendConfig = {
  customCKB?: Partial<AdvisorConfig['ckbCfg']>;
  customRule?: Partial<AdvisorConfig['ruleCfg']>;
};

export const customizeAdvisor = (props: CustomAdvisorConfig): Advisor => {
  const { charts, scopeOfCharts: CKBCfg, ruleConfig: ruleCfg } = props;

  const customCKB: ChartKnowledgeBase = {};
  charts?.forEach((chart) => {
    /** 若用户自定义的图表 id 与内置图表 id 相同，内置图表将被覆盖 */
    if (!chart.chartKnowledge.toSpec) {
      chart.chartKnowledge.toSpec = (data: any, dataProps: any) => {
        return { dataProps } as Specification;
      };
    } else {
      const oriFunc = chart.chartKnowledge.toSpec;
      chart.chartKnowledge.toSpec = (data: any, dataProps: any) => {
        return {
          ...oriFunc(data, dataProps),
          dataProps: dataProps,
        } as Specification;
      };
    }
    customCKB[chart.chartType] = chart.chartKnowledge;
  });

  // 步骤一：如果有 exclude 项，先从给到的 CKB 中剔除部分选定的图表类型
  if (CKBCfg?.exclude) {
    CKBCfg.exclude.forEach((chartType: string) => {
      if (Object.keys(customCKB).includes(chartType)) {
        delete customCKB[chartType];
      }
    });
  }
  // 步骤二：如果有 include 项，则从当前（剔除后的）CKB中，只保留 include 中的图表类型。
  if (CKBCfg?.include) {
    const include = CKBCfg.include;
    Object.keys(customCKB).forEach((chartType: string) => {
      if (!include.includes(chartType)) {
        delete customCKB[chartType];
      }
    });
  }

  const CKBConfig: CkbConfig = {
    ...CKBCfg,
    custom: customCKB,
  };
  const ruleConfig: RuleConfig = {
    ...ruleCfg,
  };

  const myAdvisor = new Advisor({
    ckbCfg: CKBConfig,
    ruleCfg: ruleConfig,
  });

  return myAdvisor;
};

/** 主推荐流程 */
export const getVisAdvices = (props: any): Advice[] => {
  const { data, dataMetaMap, myChartAdvisor } = props;
  /**
   * 若输入中有信息能够获取列的类型（ Interval, Nominal, Time ）,则将这个 信息传给 Advisor
   * 主要是读取 levelOfMeasureMents 这个字段，即 dataMetaMap[item].levelOfMeasurements
   */
  const customDataProps = dataMetaMap
    ? Object.keys(dataMetaMap).map((item) => {
        return { name: item, ...dataMetaMap[item] };
      })
    : null;
  const allAdvices = myChartAdvisor?.adviseWithLog({
    data,
    dataProps: customDataProps as AdviseParams['dataProps'],
  });
  return allAdvices?.advices ?? [];
};
