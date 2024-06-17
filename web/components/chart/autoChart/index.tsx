import { Empty, Row, Col, Select, Tooltip } from 'antd';
import { Advice, Advisor } from '@antv/ava';
import { Chart } from '@berryv/g2-react';
import i18n, { I18nKeys } from '@/app/i18n';
import { customizeAdvisor, getVisAdvices } from './advisor/pipeline';
import { useContext, useEffect, useMemo, useState } from 'react';
import { defaultAdvicesFilter } from './advisor/utils';
import { AutoChartProps, ChartType, CustomAdvisorConfig, CustomChart, Specification } from './types';
import { customCharts } from './charts';
import { ChatContext } from '@/app/chat-context';
import { compact, concat, uniq } from 'lodash';
import { sortData } from './charts/util';

const { Option } = Select;

export const AutoChart = (props: AutoChartProps) => {
  const { data, chartType, scopeOfCharts, ruleConfig } = props;

  const { mode } = useContext(ChatContext);

  const [advisor, setAdvisor] = useState<Advisor>();
  const [advices, setAdvices] = useState<Advice[]>([]);
  const [renderChartType, setRenderChartType] = useState<ChartType>();

  useEffect(() => {
    const input_charts: CustomChart[] = customCharts;
    const advisorConfig: CustomAdvisorConfig = {
      charts: input_charts,
      scopeOfCharts: {
        // 排除面积图
        exclude: ['area_chart', 'stacked_area_chart', 'percent_stacked_area_chart'],
      },
      ruleConfig,
    };
    setAdvisor(customizeAdvisor(advisorConfig));
  }, [ruleConfig, scopeOfCharts]);

  /** 将 AVA 得到的图表推荐结果和模型的合并 */
  const getMergedAdvices = (avaAdvices: Advice[]) => {
    if (!advisor) return [];
    const filteredAdvices = defaultAdvicesFilter({
      advices: avaAdvices,
    });
    const allChartTypes = uniq(
      compact(
        concat(
          chartType,
          avaAdvices.map((item) => item.type),
        ),
      ),
    );
    const allAdvices = allChartTypes
      .map((chartTypeItem) => {
        const avaAdvice = filteredAdvices.find((item) => item.type === chartTypeItem);
        // 如果在 AVA 推荐列表中，直接采用推荐列表中的结果
        if (avaAdvice) {
          return avaAdvice;
        }
        // 如果不在，则单独为其生成图表 spec
        const dataAnalyzerOutput = advisor.dataAnalyzer.execute({ data });
        if ('data' in dataAnalyzerOutput) {
          const specGeneratorOutput = advisor.specGenerator.execute({
            data: dataAnalyzerOutput.data,
            dataProps: dataAnalyzerOutput.dataProps,
            chartTypeRecommendations: [{ chartType: chartTypeItem, score: 1 }],
          });
          if ('advices' in specGeneratorOutput) return specGeneratorOutput.advices?.[0];
        }
      })
      .filter((advice) => advice?.spec) as Advice[];
    return allAdvices;
  };

  useEffect(() => {
    if (data && advisor) {
      const avaAdvices = getVisAdvices({
        data,
        myChartAdvisor: advisor,
      });
      // 合并模型推荐的图表类型和 ava 推荐的图表类型
      const allAdvices = getMergedAdvices(avaAdvices);
      setAdvices(allAdvices);
      setRenderChartType(allAdvices[0]?.type as ChartType);
    }
  }, [JSON.stringify(data), advisor, chartType]);

  const visComponent = useMemo(() => {
    /* Advices exist, render the chart. */
    if (advices?.length > 0) {
      const chartTypeInput = renderChartType ?? advices[0].type;
      const spec: Specification = advices?.find((item: Advice) => item.type === chartTypeInput)?.spec ?? undefined;
      if (spec) {
        if (spec.data && ['line_chart', 'step_line_chart'].includes(chartTypeInput)) {
          // 处理 ava 内置折线图的排序问题
          const dataAnalyzerOutput = advisor?.dataAnalyzer.execute({ data })
          if (dataAnalyzerOutput && 'dataProps' in dataAnalyzerOutput) {
            spec.data = sortData({ data: spec.data, xField: dataAnalyzerOutput.dataProps?.find(field => field.recommendation === 'date'), chartType: chartTypeInput });
          }
        }
        return (
          <Chart
            key={chartTypeInput}
            options={{
              ...spec,
              theme: mode,
              autoFit: true,
              height: 300,
            }}
          />
        );
      }
    }
  }, [advices, renderChartType]);

  if (renderChartType) {
    return (
      <div>
        <Row justify="start" className="mb-2">
          <Col>{i18n.t('Advices')}</Col>
          <Col style={{ marginLeft: 24 }}>
            <Select
              className="w-52"
              value={renderChartType}
              placeholder={'Chart Switcher'}
              onChange={(value) => setRenderChartType(value)}
              size={'small'}
            >
              {advices?.map((item) => {
                const name = i18n.t(item.type as I18nKeys);

                return (
                  <Option key={item.type} value={item.type}>
                    <Tooltip title={name} placement={'right'}>
                      <div>{name}</div>
                    </Tooltip>
                  </Option>
                );
              })}
            </Select>
          </Col>
        </Row>
        <div className="auto-chart-content">{visComponent}</div>
      </div>
    );
  }

  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={'暂无合适的可视化视图'} />;
};

export * from './helpers';
