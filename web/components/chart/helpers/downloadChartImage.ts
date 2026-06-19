import { ChartRef as G2Chart } from '@berryv/g2-react';

const getChartCanvas = (chart: G2Chart) => {
  if (!chart) return;
  const chartContainer = chart.getContainer();
  const canvasNode = chartContainer.getElementsByTagName('canvas')[0];
  return canvasNode;
};

/** Get the dataURL from a g2 Chart instance */
function toDataURL(chart: G2Chart) {
  const canvasDom = getChartCanvas(chart);
  if (canvasDom) {
    const dataURL = canvasDom.toDataURL('image/png');
    return dataURL;
  }
}

/**
 * Export chart as an image
 * @param chart chart instance
 * @param name image file name
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
