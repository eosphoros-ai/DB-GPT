import {
  CopyOutlined,
  DownloadOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons';
import { Button, Modal, Slider, Space, Tabs } from 'antd';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CodePreview } from './code-preview';

/**
 * SVG preview component is used to display SVG code and provide preview and download functionality
 * @param {Object} props The component props
 * @param {string} props.code SVG code content
 * @param {string} props.language Code language, default is svg
 */
const SvgPreview = ({ code, language = 'svg' }) => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [zoom, setZoom] = useState(100);
  const { t } = useTranslation();

  // Clean up SVG code (remove XML declaration, etc.)
  const cleanSvgCode = svgCode => {
    // Remove XML declaration
    let cleaned = svgCode.replace(/<\?xml[^>]*\?>/g, '');

    // Fix incomplete SVG tags
    if (!cleaned.includes('<svg')) {
      cleaned = `<svg xmlns="http://www.w3.org/2000/svg">${cleaned}</svg>`;
    }

    // Make sure there is a correct xmlns attribute
    if (!cleaned.includes('xmlns=') && cleaned.includes('<svg')) {
      cleaned = cleaned.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
    }

    // Make sure there is a viewBox attribute (if not)
    if (!cleaned.includes('viewBox') && cleaned.includes('<svg')) {
      // Try to create a viewBox from width and height
      const widthMatch = cleaned.match(/width=["']([^"']*)["']/);
      const heightMatch = cleaned.match(/height=["']([^"']*)["']/);

      if (widthMatch && heightMatch) {
        const width = widthMatch[1].replace(/[^\d.]/g, '');
        const height = heightMatch[1].replace(/[^\d.]/g, '');

        if (width && height) {
          cleaned = cleaned.replace('<svg', `<svg viewBox="0 0 ${width} ${height}"`);
        }
      } else {
        // If no width and height, add a default viewBox
        cleaned = cleaned.replace('<svg', '<svg viewBox="0 0 800 600"');
      }
    }

    // Make sure the closing tag is complete
    if (!cleaned.includes('</svg>')) {
      cleaned = `${cleaned}</svg>`;
    }

    return cleaned;
  };

  // Get SVG content
  const getSvgContent = () => {
    // Create a regex to match the SVG tag
    const svgRegex = /<svg[\s\S]*<\/svg>/im;
    const match = code.match(svgRegex);

    if (match) {
      // If a complete SVG tag is found, use only that part
      return cleanSvgCode(match[0]);
    } else {
      // Otherwise, try to clean up the whole code
      return cleanSvgCode(code);
    }
  };

  const showModal = () => {
    setIsModalVisible(true);
  };

  const handleCancel = () => {
    setIsModalVisible(false);
    // Reset zoom
    setZoom(100);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    });
  };

  // Download SVG file
  const downloadSVG = () => {
    // Create a Blob object
    const blob = new Blob([getSvgContent()], { type: 'image/svg+xml' });

    // Create a URL object
    const url = URL.createObjectURL(blob);

    // Create an a tag
    const a = document.createElement('a');
    a.href = url;
    a.download = 'image.svg'; // 文件名

    // Add to body and trigger click
    document.body.appendChild(a);
    a.click();

    // Clean up
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Download PNG file
  const downloadPNG = () => {
    // Create a canvas
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    // Create an image element
    const img = new Image();
    const svgBlob = new Blob([getSvgContent()], { type: 'image/svg+xml' });
    const url = URL.createObjectURL(svgBlob);

    img.onload = () => {
      // Resize the canvas to match the SVG size
      canvas.width = img.width;
      canvas.height = img.height;

      // Draw the SVG to the canvas
      ctx.drawImage(img, 0, 0);

      // Try to convert to PNG and download
      try {
        const pngUrl = canvas.toDataURL('image/png');

        const a = document.createElement('a');
        a.href = pngUrl;
        a.download = 'image.png';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } catch (e) {
        console.error('PNG export failed:', e);
      }

      // Clean up
      URL.revokeObjectURL(url);
    };

    img.src = url;
  };

  // Control zoom
  const handleZoomChange = value => {
    setZoom(value);
  };

  const zoomIn = () => {
    setZoom(Math.min(zoom + 10, 200));
  };

  const zoomOut = () => {
    setZoom(Math.max(zoom - 10, 50));
  };

  const resetZoom = () => {
    setZoom(100);
  };

  // Create tab items
  const getTabItems = () => {
    const items = [
      {
        key: 'preview',
        label: t('code_preview'),
        children: (
          <div className='relative'>
            <div className='flex justify-center items-center p-4 bg-gray-100 dark:bg-gray-800 min-h-[60vh] overflow-auto'>
              <div className='relative bg-white dark:bg-gray-700 p-4 shadow-md rounded flex items-center justify-center'>
                <div
                  className='transition-transform duration-200'
                  style={{
                    transform: `scale(${zoom / 100})`,
                    transformOrigin: 'center center',
                    maxWidth: '100%',
                    maxHeight: '100%',
                  }}
                >
                  <div
                    className='svg-container'
                    dangerouslySetInnerHTML={{ __html: getSvgContent() }}
                    style={{
                      maxWidth: '100%',
                      margin: '0 auto',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  />
                </div>
              </div>
            </div>
            <div className='flex items-center justify-center p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800'>
              <Space>
                <Button icon={<ZoomOutOutlined />} onClick={zoomOut} disabled={zoom <= 50} />
                <Slider min={50} max={200} value={zoom} onChange={handleZoomChange} style={{ width: 200 }} />
                <Button icon={<ZoomInOutlined />} onClick={zoomIn} disabled={zoom >= 200} />
                <Button icon={<ReloadOutlined />} onClick={resetZoom} disabled={zoom === 100} />
                <span className='text-sm text-gray-500 dark:text-gray-400 min-w-[50px]'>{zoom}%</span>
              </Space>
            </div>
          </div>
        ),
      },
      {
        key: 'code',
        label: t('code_preview_code'),
        children: (
          <div className='p-4'>
            <CodePreview code={code} language='svg' />
          </div>
        ),
      },
    ];

    return items;
  };

  return (
    <div className='relative'>
      {/* Code preview section */}
      <CodePreview code={code} language={language} />

      {/* Operation button */}
      <div className='absolute bottom-2 right-2 flex gap-2'>
        <Button
          type='text'
          icon={<CopyOutlined />}
          onClick={copyToClipboard}
          className='flex items-center justify-center bg-opacity-70 hover:bg-opacity-100 transition-all'
          size='small'
        >
          {isCopied ? t('code_preview_already_copied') : t('code_preview_copy')}
        </Button>
        <Button
          type='text'
          icon={<DownloadOutlined />}
          onClick={downloadSVG}
          className='flex items-center justify-center bg-opacity-70 hover:bg-opacity-100 transition-all'
          size='small'
        >
          {t('code_preview_download')}
        </Button>
        <Button
          type='primary'
          icon={<PlayCircleOutlined />}
          onClick={showModal}
          className='flex items-center justify-center bg-opacity-70 hover:bg-opacity-100 transition-all'
          size='small'
        >
          {t('code_preview')}
        </Button>
      </div>

      {/* Preview modal */}
      <Modal
        title={'SVG ' + t('code_preview')}
        open={isModalVisible}
        onCancel={handleCancel}
        footer={[
          <Button key='svg' icon={<DownloadOutlined />} onClick={downloadSVG}>
            {t('code_preview_download')} SVG
          </Button>,
          <Button key='png' onClick={downloadPNG}>
            {t('code_preview_download')} PNG
          </Button>,
          <Button key='close' onClick={handleCancel}>
            {t('code_preview_close')}
          </Button>,
        ]}
        width={800}
        bodyStyle={{ padding: 0 }}
      >
        <Tabs defaultActiveKey='preview' items={getTabItems()} />
      </Modal>
    </div>
  );
};

export default SvgPreview;
