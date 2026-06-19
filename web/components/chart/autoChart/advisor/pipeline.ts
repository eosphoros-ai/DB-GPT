import type { Advice, AdviseParams, AdvisorConfig, ChartKnowledgeBase, Datum, FieldInfo } from '@antv/ava';
import { Advisor, CkbConfig, DataFrame } from '@antv/ava';
import { size } from 'lodash';
import type { CustomAdvisorConfig, RuleConfig, Specification } from '../types';

export type CustomRecommendConfig = {
  customCKB?: Partial<AdvisorConfig['ckbCfg']>;
  customRule?: Partial<AdvisorConfig['ruleCfg']>;
};

export const customizeAdvisor = (props: CustomAdvisorConfig): Advisor => {
  const { charts, scopeOfCharts: CKBCfg, ruleConfig: ruleCfg } = props;

  const customCKB: ChartKnowledgeBase = {};
  charts?.forEach(chart => {
    /** If a custom chart id matches a built-in chart id, the built-in chart is overridden */
    if (!chart.chartKnowledge.toSpec) {
      chart.chartKnowledge.toSpec = (_: any, dataProps: any) => {
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

  // Step 1: If exclude is set, remove those chart types from the CKB
  if (CKBCfg?.exclude) {
    CKBCfg.exclude.forEach((chartType: string) => {
      if (Object.keys(customCKB).includes(chartType)) {
        delete customCKB[chartType];
      }
    });
  }
  // Step 2: If include is set, keep only those chart types in the (filtered) CKB
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

/** Main recommendation pipeline */
export const getVisAdvices = (props: {
  data: Datum[];
  myChartAdvisor: Advisor;
  dataMetaMap?: Record<string, FieldInfo>;
}): Advice[] => {
  const { data, dataMetaMap, myChartAdvisor } = props;
  /**
   * If column types (Interval, Nominal, Time) are available in the input, pass them to Advisor.
   * Reads levelOfMeasurements from dataMetaMap[item].levelOfMeasurements.
   */
  const customDataProps = dataMetaMap
    ? Object.keys(dataMetaMap).map(item => {
        return { name: item, ...dataMetaMap[item] };
      })
    : null;

  // Optionally use all fields for recommendations
  const useAllFields = false;
  // Select fields with more than one distinct dimension value
  const allFieldsInfo = new DataFrame(data).info();
  const selectedFields =
    size(allFieldsInfo) > 2
      ? allFieldsInfo?.filter(field => {
          if (field.recommendation === 'string' || field.recommendation === 'date') {
            return field.distinct && field.distinct > 1;
          }
          return true;
        })
      : allFieldsInfo;

  const allAdvices = myChartAdvisor?.adviseWithLog({
    data,
    dataProps: customDataProps as AdviseParams['dataProps'],
    // Omit fields to use all fields by default; otherwise use the selected business fields
    fields: useAllFields ? undefined : selectedFields?.map(field => field.name),
  });
  return allAdvices?.advices ?? [];
};
