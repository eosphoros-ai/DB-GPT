import { ChatContext } from '@/app/chat-context';
import i18n, { I18nKeys } from '@/app/i18n';
import { DownloadOutlined } from '@ant-design/icons';
import { Advice, Advisor, Datum } from '@antv/ava';
import { Chart, ChartRef } from '@berryv/g2-react';
import { Button, Col, Empty, Row, Select, Space, Tooltip } from 'antd';
import { compact, concat, uniq } from 'lodash';
import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { downloadImage } from '../helpers/downloadChartImage';
import { customizeAdvisor, getVisAdvices } from './advisor/pipeline';
import { defaultAdvicesFilter } from './advisor/utils';
import { customCharts } from './charts';
import { processNilData, sortData } from './charts/util';
import { AutoChartProps, ChartType, CustomAdvisorConfig, CustomChart, Specification } from './types';
const { Option } = Select;

export const AutoChart = (props: AutoChartProps) => {
  const { data: originalData, chartType, scopeOfCharts, ruleConfig } = props;
  // Handle empty values (data marked as '-')
  const data = processNilData(originalData) as Datum[];
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
        // Exclude area charts
        exclude: ['area_chart', 'stacked_area_chart', 'percent_stacked_area_chart'],
      },
      ruleConfig,
    };
    setAdvisor(customizeAdvisor(advisorConfig));
  }, [ruleConfig, scopeOfCharts]);

  /** Merge AVA chart recommendations with model recommendations */
  const getMergedAdvices = (avaAdvices: Advice[]) => {
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
        // If in the AVA recommendation list, use that result directly
        if (avaAdvice) {
          return avaAdvice;
        }
        // Otherwise, generate a chart spec for this type separately
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
  };

  useEffect(() => {
    if (data && advisor) {
      const avaAdvices = getVisAdvices({
        data,
        myChartAdvisor: advisor,
      });
      // Merge model-recommended chart types with AVA recommendations
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
          // Fix sorting for built-in AVA line charts
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
          // Add pie chart tooltip title display
          spec.tooltip = { title: { field: spec.encode.color } };
        }
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
  }, [advices, mode, renderChartType]);

  if (renderChartType) {
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

  return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={'No suitable visualization available'} />;
};

export * from './helpers';
