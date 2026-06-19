import { ChatContext } from '@/app/chat-context';
import { useSearchParams } from 'next/navigation';
import { useContext, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

const Libro: React.FC = () => {
  const searchParams = useSearchParams();
  const { i18n } = useTranslation();
  const { mode } = useContext(ChatContext);
  const iframeRef = useRef<HTMLIFrameElement | null>(null);

  const id = searchParams?.get('id') || '';

  useEffect(() => {
    console.log(window.location);
    // Listen for language switch events
    const handleLanguageChange = (lng: string) => {
      iframeRef.current?.contentWindow?.postMessage(
        `lang:${lng}`,
        `${window.location.protocol}//${window.location.hostname}:5671`,
      );
    };

    // Register listener
    i18n.on('languageChanged', handleLanguageChange);

    // Clean up listener
    return () => {
      i18n.off('languageChanged', handleLanguageChange);
    };
  }, []);

  useEffect(() => {
    iframeRef.current?.contentWindow?.postMessage(
      `theme:${mode}`,
      `${window.location.protocol}//${window.location.hostname}:5671`,
    );
  }, [mode]);

  return (
    <>
      <iframe
        src={`${window.location.protocol}//${window.location.hostname}:5671/dbgpt?flow_uid=${id}`}
        className='h-full'
        ref={iframeRef}
      ></iframe>
    </>
  );
};

export default Libro;
