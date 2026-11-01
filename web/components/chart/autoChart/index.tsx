import { ChatContext } from '@/app/chat-context';
import i18n, { I18nKeys } from '@/app/i18n';
import { DownloadOutlined } from '@ant-design/icons';
import { Advice, Advisor, Datum } from '@antv/ava';
import { Chart, ChartRef } from '@berryv/g2-react';
import { Button, Col, Empty, Row, Select, Space, Tooltip } from 'antd';
import { compact, concat, uniq } from 'lodash';
import { MutableRefObject, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { downloadImage } from '../helpers/downloadChartImage';
import { customizeAdvisor, getVisAdvices } from './advisor/pipeline';
import { defaultAdvicesFilter } from './advisor/utils';
import { customCharts } from './charts';
import { processNilData, sortData } from './charts/util';
import { AutoChartProps, ChartType, CustomAdvisorConfig, CustomChart, Specification } from './types';
const { Option } = Select;

/** Observe the existing G2 render promise; do not replace its renderer. */
const ObservedChart = ({
  options,
  chartRef,
  onObservation,
}: {
  options: Specification;
  chartRef: MutableRefObject<ChartRef | undefined>;
  onObservation: NonNullable<AutoChartProps['onRenderObservation']>;
}) => {
  const [ready, setReady] = useState(false);
  const callback = useRef(onObservation);
  callback.current = onObservation;
  const onInit = useCallback(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const original = chart.render.bind(chart);
    chart.render = (...args: Parameters<typeof original>) => {
      const started = performance.now();
      const finish = (error?: unknown) => {
        let runtimeOptions: Record<string, unknown> | undefined;
        try {
          runtimeOptions = JSON.parse(JSON.stringify(chart.options()));
        } catch {
          /* Functions cannot be serialized. */
        }
        callback.current({
          renderer: 'g2',
          state: error ? 'failed' : 'rendered',
          duration_ms: Math.max(0, Math.round(performance.now() - started)),
          options: runtimeOptions,
          ...(error ? { error: String(error).slice(0, 2000) } : {}),
        });
      };
      try {
        const result = original(...args);
        void Promise.resolve(result).then(
          () => finish(),
          error => finish(error),
        );
        return result;
      } catch (error) {
        finish(error);
        throw error;
      }
    };
    setReady(true);
  }, [chartRef]);
  return <Chart ref={chartRef} onInit={onInit} options={ready ? options : undefined} />;
};

export const AutoChart = (props: AutoChartProps) => {
  const { data: originalData, chartType, scopeOfCharts, ruleConfig, showControls = true, onRenderObservation } = props;
  // 处理空值数据 (为'-'的数据)
  const data = useMemo(() => processNilData(originalData) as Datum[], [originalData]);
  const { mode } = useContext(ChatContext);

  const [advisor, setAdvisor] = useState<Advisor>();
  const [advices, setAdvices] = useState<Advice[]>([]);
  const [renderChartType, setRenderChartType] = useState<ChartType>();
  const chartRef = useRef<ChartRef>();

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
  const getMergedAdvices = useCallback(
    (avaAdvices: Advice[]) => {
      if (!advisor) return [];
      const filteredAdvices = defaultAdvicesFilter({
        advices: avaAdvices,
      });
      const allChartTypes = uniq(
        compact(
          concat(
            chartType,
            avaAdvices.map(item => item.type),
          ),
        ),
      );
      const allAdvices = allChartTypes
        .map(chartTypeItem => {
          const avaAdvice = filteredAdvices.find(item => item.type === chartTypeItem);
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
        .filter(advice => advice?.spec) as Advice[];
      return allAdvices;
    },
    [advisor, chartType, data],
  );

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
      if (!allAdvices.length && onRenderObservation)
        onRenderObservation({
          renderer: 'g2',
          state: 'not_rendered',
          error: 'No applicable visualization specification',
        });
    }
  }, [data, advisor, getMergedAdvices, onRenderObservation]);

  const visComponent = useMemo(() => {
    /* Advices exist, render the chart. */
    if (advices?.length > 0) {
      const chartTypeInput = renderChartType ?? advices[0].type;
      const spec: Specification = advices?.find((item: Advice) => item.type === chartTypeInput)?.spec ?? undefined;
      if (spec) {
        if (spec.data && ['line_chart', 'step_line_chart'].includes(chartTypeInput)) {
          // 处理 ava 内置折线图的排序问题
          const dataAnalyzerOutput = advisor?.dataAnalyzer.execute({ data });
          if (dataAnalyzerOutput && 'dataProps' in dataAnalyzerOutput) {
            spec.data = sortData({
              data: spec.data,
              xField: dataAnalyzerOutput.dataProps?.find((field: any) => field.recommendation === 'date'),
              chartType: chartTypeInput,
            });
          }
        }
        if (chartTypeInput === 'pie_chart' && spec?.encode?.color) {
          // 补充饼图的 tooltip title 展示
          spec.tooltip = { title: { field: spec.encode.color } };
        }
        const options = { ...spec, autoFit: true, theme: mode, height: 300 };
        if (onRenderObservation)
          return (
            <ObservedChart
              key={chartTypeInput}
              options={options}
              chartRef={chartRef}
              onObservation={onRenderObservation}
            />
          );
        return (
          <Chart
            key={chartTypeInput}
            options={{
              ...spec,
              autoFit: true,
              theme: mode,
              height: 300,
            }}
            ref={chartRef}
          />
        );
      }
    }
  }, [advices, mode, renderChartType, onRenderObservation, advisor, data]);

  if (renderChartType) {
    if (!showControls) return <div className='flex'>{visComponent}</div>;
    return (
      <div>
        <Row justify='space-between' className='mb-2'>
          <Col>
            <Space>
              <span>{i18n.t('Advices')}</span>
              <Select
                className='w-52'
                value={renderChartType}
                placeholder={'Chart Switcher'}
                onChange={value => setRenderChartType(value)}
                size={'small'}
              >
                {advices?.map(item => {
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
            </Space>
          </Col>
          <Col>
            <Tooltip title={i18n.t('Download')}>
              <Button
                onClick={() => downloadImage(chartRef.current, i18n.t(renderChartType as I18nKeys))}
                icon={<DownloadOutlined />}
                type='text'
              />
            </Tooltip>
          </Col>
        </Row>
        <div className='flex'>{visComponent}</div>
      </div>
    );
  }

  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={'暂无合适的可视化视图'} />;
};

export * from './helpers';
