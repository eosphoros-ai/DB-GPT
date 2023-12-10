import { Empty, Row, Col, Select, Tooltip } from 'antd';
import { Advice, Advisor } from '@antv/ava';
import { Chart } from '@berryv/g2-react';
import { DownOutlined } from '@ant-design/icons';
import i18n from '@/app/i18n';
import { customizeAdvisor, getVisAdvices } from './advisor/pipeline';
import { useEffect, useMemo, useState } from 'react';
import { defaultAdvicesFilter } from './advisor/utils';
import { AutoChartProps, ChartType, CustomAdvisorConfig, CustomChart, Specification } from './types';
import { customCharts } from './charts';

const { Option } = Select;

export const AutoChart = (props: AutoChartProps) => {
  const { data, chartType, scopeOfCharts, ruleConfig } = props;

  const [advisor, setAdvisor] = useState<Advisor>();
  const [advices, setAdvices] = useState<Advice[]>([]);
  const [renderChartType, setRenderChartType] = useState<ChartType>();

  useEffect(() => {
    const input_charts: CustomChart[] = customCharts;
    const advisorConfig: CustomAdvisorConfig = {
      charts: input_charts,
      scopeOfCharts: undefined,
      ruleConfig,
    };
    setAdvisor(customizeAdvisor(advisorConfig));
  }, [ruleConfig, scopeOfCharts]);

  useEffect(() => {
    if (data && advisor) {
      const avaAdvices = getVisAdvices({
        data,
        myChartAdvisor: advisor,
      });
      const filteredAdvices = defaultAdvicesFilter({
        advices: avaAdvices,
      });

      filteredAdvices.sort((a, b) => {
        return chartType.indexOf(b.type) - chartType?.indexOf(a.type);
      });

      setAdvices(filteredAdvices);

      setRenderChartType(filteredAdvices[0]?.type as ChartType);
    }
  }, [data, advisor, chartType]);

  const visComponent = useMemo(() => {
    /* Advices exist, render the chart. */
    if (advices?.length > 0) {
      const chartTypeInput = renderChartType ?? advices[0].type;
      const spec: Specification = advices?.find((item: Advice) => item.type === chartTypeInput)?.spec ?? undefined;
      if (spec) {
        return <Chart key={chartTypeInput} options={spec} />;
      }
    }
  }, [advices, renderChartType]);

  if (renderChartType) {
    return (
      <div>
        <Row justify="start">
          <Col>{i18n.t('Advices')}</Col>
          <Col style={{ marginLeft: 24 }}>
            <Select
              value={renderChartType}
              placeholder={'Chart Switcher'}
              style={{ width: '180px' }}
              onChange={(value) => setRenderChartType(value)}
              size={'small'}
            >
              {advices?.map((item) => {
                const name = i18n.t(item.type);

                return (
                  <Option key={item.type} value={item.type}>
                    <Tooltip title={name} placement={'right'}>
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <DownOutlined />
                        <div style={{ marginLeft: '2px' }}>{name}</div>
                      </div>
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
