import { ChartRef as G2Chart } from '@berryv/g2-react';

const getChartCanvas = (chart: G2Chart) => {
  if (!chart) return;
  const chartContainer = chart.getContainer();
  const canvasNode = chartContainer.getElementsByTagName('canvas')[0];
  return canvasNode;
};

/** 获得 g2 Chart 实例的 dataURL */
function toDataURL(chart: G2Chart) {
  const canvasDom = getChartCanvas(chart);
  if (canvasDom) {
    const dataURL = canvasDom.toDataURL('image/png');
    return dataURL;
  }
}

/**
 * 图表图片导出
 * @param chart chart 实例
 * @param name 图片名称
 */
export function downloadImage(chart: G2Chart, name: string = 'Chart') {
  const link = document.createElement('a');
  const filename = `${name}.png`;

  setTimeout(() => {
    const dataURL = toDataURL(chart);
    if (dataURL) {
      link.addEventListener('click', () => {
        link.download = filename;
        link.href = dataURL;
      });
      const e = document.createEvent('MouseEvents');
      e.initEvent('click', false, false);
      link.dispatchEvent(e);
    }
  }, 16);
}
