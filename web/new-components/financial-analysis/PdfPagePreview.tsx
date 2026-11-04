import { Alert, Button, InputNumber, Space, Spin } from 'antd';
import React, { useEffect, useState } from 'react';
import { financialText, useFinancialLocale } from './i18n';
import type { EvidenceExcerpt, SourceDocument, SourcePreviewAccess } from './types';

export const evidencePages = (evidence: EvidenceExcerpt) =>
  [...new Set([evidence.page, evidence.headerPage, evidence.unitPage])].filter(
    (page): page is number => page !== undefined && Number.isInteger(page) && page > 0,
  );

const PdfPagePreview: React.FC<{
  evidence: EvidenceExcerpt;
  document: SourceDocument;
  access: SourcePreviewAccess;
}> = ({ evidence, document, access }) => {
  useFinancialLocale();
  const [page, setPage] = useState(evidence.page);
  const [image, setImage] = useState<{ page: number; url: string } | null>(null);
  const [error, setError] = useState('');
  const [downloadError, setDownloadError] = useState('');
  const [downloading, setDownloading] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    let url: string | undefined;
    setImage(null);
    setError('');
    access
      .loadPage(document.id, page, controller.signal)
      .then(blob => {
        if (controller.signal.aborted) return;
        url = URL.createObjectURL(blob);
        setImage({ page, url });
      })
      .catch(cause => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : financialText('financial.page_failed_to_load'));
      });
    return () => {
      controller.abort();
      if (url) URL.revokeObjectURL(url);
    };
  }, [access, document.id, page, retry]);

  const download = async () => {
    setDownloading(true);
    setDownloadError('');
    try {
      await access.download(document);
    } catch (cause) {
      setDownloadError(cause instanceof Error ? cause.message : financialText('financial.download_failed'));
    } finally {
      setDownloading(false);
    }
  };
  return (
    <section aria-label={financialText('financial.original_pdf_page')}>
      <Space wrap className='mb-3'>
        <Button disabled={page <= 1} onClick={() => setPage(value => value - 1)}>
          {financialText('financial.previous_page')}
        </Button>
        <label>
          {financialText('financial.physical_page')}{' '}
          <InputNumber
            aria-label={financialText('financial.pdf_physical_page_number')}
            min={1}
            max={document.pageCount}
            precision={0}
            value={page}
            onChange={value => {
              if (
                value !== null &&
                Number.isInteger(value) &&
                value >= 1 &&
                (!document.pageCount || value <= document.pageCount)
              )
                setPage(value);
            }}
          />
        </label>
        <span>
          / {document.pageCount ?? financialText('financial.unknown')} {financialText('financial.page')}
        </span>
        <Button
          disabled={!document.pageCount || page >= document.pageCount}
          onClick={() => setPage(value => value + 1)}
        >
          {financialText('financial.next_page')}
        </Button>
        <Button loading={downloading} onClick={() => void download()}>
          {financialText('financial.download_original_pdf')}
        </Button>
      </Space>
      <p>{financialText('financial.original_pdf_image_counted_from_page_1_numbering_may_differ_from_pri')}</p>
      <Space wrap className='mb-3'>
        {evidencePages(evidence).map(target => (
          <Button key={target} size='small' onClick={() => setPage(target)}>
            {target === evidence.page
              ? financialText('financial.metric_page')
              : target === evidence.headerPage
                ? financialText('financial.header_page')
                : financialText('financial.unit_page')}{' '}
            {target}
          </Button>
        ))}
      </Space>
      {downloadError && <Alert type='error' message={downloadError} />}
      {error ? (
        <Alert
          type='warning'
          message={error}
          description={financialText('financial.source_value_physical_page_value_excerpts_below_remain_available_for', {
            value1: document.fileName,
            value2: page,
          })}
          action={<Button onClick={() => setRetry(value => value + 1)}>{financialText('financial.retry')}</Button>}
        />
      ) : image?.page === page ? (
        // Original PDF raster, not an optimized remote web image.
        <img
          src={image.url}
          alt={financialText('financial.value_pdf_physical_page_value', { value1: document.fileName, value2: page })}
          style={{ width: '100%', height: 'auto' }}
          onError={() =>
            setError(financialText('financial.the_page_image_failed_to_load_retry_or_download_the_original_pdf'))
          }
        />
      ) : (
        <div role='status' className='p-8'>
          <Spin /> {financialText('financial.loading_physical_page')}
          {page} {financialText('financial.page')}
        </div>
      )}
    </section>
  );
};
export default PdfPagePreview;
