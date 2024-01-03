import { BackEndChartType } from '@/components/chart';
import ChartView from './chart-view';
import { Datum } from '@antv/ava';

interface Props {
  data: {
    data: Datum[];
    describe: string;
    title: string;
    type: BackEndChartType;
    sql: string;
  };
}

function VisChart({ data }: Props) {
  return <ChartView data={data.data} type={data.type} sql={data.sql} />;
}

export default VisChart;
