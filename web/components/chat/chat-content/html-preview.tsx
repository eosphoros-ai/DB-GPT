import {
  CopyOutlined,
  DownloadOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { Button, Modal, Tabs } from 'antd';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { CodePreview } from './code-preview';
/**
 * The HTML preview component is used to display HTML code and provide run, download, and full-screen functionality
 * @param {Object} props The component props
 * @param {string} props.code HTML code content
 * @param {string} props.language Code language, default is html
 */
const HtmlPreview = ({ code, language = 'html' }) => {
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const iframeRef = useRef(null);
  const { t } = useTranslation();
  const [parsedCode, setParsedCode] = useState({
    html: '',
    css: '',
    js: '',
    fullCode: '',
  });

  // Parse the code and extract the HTML, CSS, and JS parts
  useEffect(() => {
    const parseCode = sourceCode => {
      let html = sourceCode;
      let css = '';
      let js = '';

      // Parse the content inside the <style> tags
      const styleRegex = /<style[^>]*>([\s\S]*?)<\/style>/gi;
      const styleMatches = [...sourceCode.matchAll(styleRegex)];

      if (styleMatches.length > 0) {
        // Remove the style tags
        styleMatches.forEach(match => {
          css += match[1] + '\n';
          html = html.replace(match[0], '');
        });
      }

      // Parse the content inside the <script> tags
      const scriptRegex = /<script[^>]*>([\s\S]*?)<\/script>/gi;
      const scriptMatches = [...sourceCode.matchAll(scriptRegex)];

      if (scriptMatches.length > 0) {
        // Remove the script tags
        scriptMatches.forEach(match => {
          js += match[1] + '\n';
          html = html.replace(match[0], '');
        });
      }

      // Create the full HTML document
      let fullCode = sourceCode;

      // If it's not a complete HTML document, wrap it
      if (!sourceCode.includes('<!DOCTYPE html>') && !sourceCode.includes('<html')) {
        fullCode = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>HTML Preview</title>
  ${styleMatches.length > 0 ? styleMatches.map(m => m[0]).join('\n') : ''}
</head>
<body>
  ${html}
  ${scriptMatches.length > 0 ? scriptMatches.map(m => m[0]).join('\n') : ''}
</body>
</html>`;
      }

      return {
        html,
        css,
        js,
        fullCode,
      };
    };

    setParsedCode(parseCode(code));
  }, [code]);

  // Listen for fullscreen change events
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(
        document.fullscreenElement ||
          document.webkitFullscreenElement ||
          document.mozFullScreenElement ||
          document.msFullscreenElement,
      );
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
      document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
      document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    };
  }, []);

  const showModal = () => {
    setIsModalVisible(true);
  };

  const handleCancel = () => {
    // If in full screen mode, exit first
    if (isFullscreen) {
      exitFullscreen();
    }
    setIsModalVisible(false);
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(code).then(() => {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    });
  };

  // Download the HTML file
  const downloadHTML = () => {
    // Create a Blob object
    const blob = new Blob([parsedCode.fullCode], { type: 'text/html' });

    // Create a URL object
    const url = URL.createObjectURL(blob);

    // Create an a tag
    const a = document.createElement('a');
    a.href = url;
    a.download = 'preview.html'; // File name

    // Add to body and trigger click
    document.body.appendChild(a);
    a.click();

    // Clean up
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  // Toggle fullscreen mode
  const toggleFullscreen = () => {
    if (isFullscreen) {
      exitFullscreen();
    } else {
      enterFullscreen();
    }
  };

  // Enter fullscreen mode
  const enterFullscreen = () => {
    const elem = iframeRef.current;
    if (!elem) return;

    if (elem.requestFullscreen) {
      elem.requestFullscreen();
    } else if (elem.webkitRequestFullscreen) {
      /* Safari */
      elem.webkitRequestFullscreen();
    } else if (elem.msRequestFullscreen) {
      /* IE11 */
      elem.msRequestFullscreen();
    } else if (elem.mozRequestFullScreen) {
      /* Firefox */
      elem.mozRequestFullScreen();
    }
  };

  // Exit fullscreen mode
  const exitFullscreen = () => {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    } else if (document.webkitExitFullscreen) {
      /* Safari */
      document.webkitExitFullscreen();
    } else if (document.msExitFullscreen) {
      /* IE11 */
      document.msExitFullscreen();
    } else if (document.mozCancelFullScreen) {
      /* Firefox */
      document.mozCancelFullScreen();
    }
  };

  // Create tab items
  const getTabItems = () => {
    const items = [
      {
        key: 'preview',
        label: t('code_preview'),
        children: (
          <div className='relative'>
            <iframe
              ref={iframeRef}
              srcDoc={parsedCode.fullCode}
              style={{ width: '100%', height: '60vh', border: 'none' }}
              sandbox='allow-scripts allow-same-origin'
              title='HTML Preview'
            />
            <Button
              type='primary'
              icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
              onClick={toggleFullscreen}
              className='absolute top-2 right-2 z-10'
              size='small'
            >
              {isFullscreen ? t('code_preview_exit_full_screen') : t('code_preview_full_screen')}
            </Button>
          </div>
        ),
      },
    ];

    // Only show the code tab when the code is parsed into multiple parts
    if (parsedCode.html || parsedCode.css || parsedCode.js) {
      items.push({
        key: 'code',
        label: t('code_preview_code'),
        children: (
          <div className='p-4'>
            {parsedCode.html && (
              <div className='mb-4'>
                <h3 className='text-lg font-medium mb-2'>HTML</h3>
                <CodePreview code={parsedCode.html} language='html' />
              </div>
            )}
            {parsedCode.css && (
              <div className='mb-4'>
                <h3 className='text-lg font-medium mb-2'>CSS</h3>
                <CodePreview code={parsedCode.css} language='css' />
              </div>
            )}
            {parsedCode.js && (
              <div className='mb-4'>
                <h3 className='text-lg font-medium mb-2'>JavaScript</h3>
                <CodePreview code={parsedCode.js} language='javascript' />
              </div>
            )}
          </div>
        ),
      });
    }

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
          onClick={downloadHTML}
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
          {t('code_preview_run')}
        </Button>
      </div>

      {/* Run preview modal */}
      <Modal
        title={'HTML ' + t('code_preview')}
        open={isModalVisible}
        onCancel={handleCancel}
        footer={[
          <Button key='download' icon={<DownloadOutlined />} onClick={downloadHTML}>
            {t('code_preview_download')} HTML
          </Button>,
          <Button
            key='fullscreen'
            icon={isFullscreen ? <FullscreenExitOutlined /> : <FullscreenOutlined />}
            onClick={toggleFullscreen}
          >
            {isFullscreen ? t('code_preview_exit_full_screen') : t('code_preview_full_screen')}
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

export default HtmlPreview;
