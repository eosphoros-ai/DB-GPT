import classNames from 'classnames';
import React, { useMemo } from 'react';
import { useTranslation } from 'react-i18next';

export interface ObservationFormatterProps {
  observation: string;
  className?: string;
}

interface ParsedObservation {
  type: 'shape' | 'columns' | 'dtypes' | 'preview' | 'raw';
  data: any;
  original: string;
}

const parseObservation = (obsText: string): ParsedObservation | null => {
  try {
    const jsonMatch = obsText.match(/Observation:\s*(\{[\s\S]*\})/);
    if (!jsonMatch) return null;

    const data = JSON.parse(jsonMatch[1]);

    if (data.shape && Array.isArray(data.shape)) {
      return { type: 'shape', data, original: obsText };
    }

    if (data.columns && Array.isArray(data.columns)) {
      return { type: 'columns', data, original: obsText };
    }

    if (data.dtypes) {
      return { type: 'dtypes', data, original: obsText };
    }

    if (data.preview || data.head || data.data) {
      return { type: 'preview', data, original: obsText };
    }

    return { type: 'raw', data, original: obsText };
  } catch {
    return null;
  }
};

const ObservationFormatter: React.FC<ObservationFormatterProps> = ({ observation, className }) => {
  const parsed = useMemo(() => parseObservation(observation), [observation]);

  if (!parsed) return null;

  const renderContent = () => {
  const { t } = useTranslation();
    switch (parsed.type) {
      case 'shape':
        return (
          <div className='space-y-2'>
            <div className='flex items-center gap-2'>
              <span className='text-lg'>📊</span>
              <span className='text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase'>{t('ui_6d90a2a6')}</span>
            </div>
            <div className='space-y-1.5 text-sm'>
              {parsed.data.shape && (
                <div className='flex items-center gap-2'>
                  <span className='text-gray-500 dark:text-gray-400'>•</span>
                  <span className='text-gray-700 dark:text-gray-300'>{t('ui_5162731a')}<span className='font-mono font-medium text-blue-600 dark:text-blue-400 ml-1'>
                      {parsed.data.shape[0]} 行 × {parsed.data.shape[1]} {{parsed.data.shape[1]}}{t('ui_cb2f68c9')}</span>
                  </span>
                </div>
              )}
              {parsed.data.columns && parsed.data.columns.length > 0 && (
                <div className='flex items-start gap-2'>
                  <span className='text-gray-500 dark:text-gray-400 mt-0.5'>•</span>
                  <div className='flex-1'>
                    <span className='text-gray-700 dark:text-gray-300'>{t('ui_26fbd5d7')}</span>
                    <div className='flex flex-wrap gap-1.5 mt-1'>
                      {parsed.data.columns.slice(0, 10).map((col: string, idx: number) => (
                        <span
                          key={idx}
                          className='px-2 py-0.5 text-xs font-mono rounded bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300'
                        >
                          {col}
                        </span>
                      ))}
                      {parsed.data.columns.length > 10 && (
                        <span className='text-xs text-gray-500 dark:text-gray-400 self-center'>
                          +{parsed.data.columns.length - 10} more
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        );

      case 'dtypes':
        return (
          <div className='space-y-2'>
            <div className='flex items-center gap-2'>
              <span className='text-lg'>🔍</span>
              <span className='text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase'>{t('ui_185f7bf6')}</span>
            </div>
            <div className='grid grid-cols-1 gap-1 text-sm'>
              {Object.entries(parsed.data.dtypes || parsed.data)
                .slice(0, 8)
                .map(([key, value], idx) => (
                  <div key={idx} className='flex items-center gap-2 py-1'>
                    <span className='font-mono text-xs text-gray-600 dark:text-gray-400 min-w-[100px]'>{key}</span>
                    <span className='text-xs px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 font-medium'>
                      {String(value)}
                    </span>
                  </div>
                ))}
            </div>
          </div>
        );

      case 'columns':
        return (
          <div className='space-y-2'>
            <div className='flex items-center gap-2'>
              <span className='text-lg'>📋</span>
              <span className='text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase'>{t('ui_20aadc3f')}</span>
            </div>
            <div className='flex flex-wrap gap-1.5'>
              {parsed.data.columns.slice(0, 12).map((col: string, idx: number) => (
                <span
                  key={idx}
                  className='px-2 py-1 text-xs font-mono rounded bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800'
                >
                  {col}
                </span>
              ))}
              {parsed.data.columns.length > 12 && (
                <span className='px-2 py-1 text-xs text-gray-500 dark:text-gray-400'>
                  +{parsed.data.columns.length - 12} more
                </span>
              )}
            </div>
          </div>
        );

      case 'raw':
      default:
        return (
          <div className='space-y-2'>
            <div className='flex items-center gap-2'>
              <span className='text-lg'>📄</span>
              <span className='text-xs font-semibold text-gray-600 dark:text-gray-400 uppercase'>{t('ui_0cb08950')}</span>
            </div>
            <pre className='text-xs font-mono text-gray-700 dark:text-gray-300 overflow-x-auto p-2 bg-gray-50 dark:bg-gray-900/50 rounded'>
              {JSON.stringify(parsed.data, null, 2)}
            </pre>
          </div>
        );
    }
  };

  return (
    <div
      className={classNames(
        'rounded-lg px-4 py-3 mb-3',
        'border border-amber-200 dark:border-amber-800/50',
        'bg-amber-50/30 dark:bg-amber-900/10',
        className,
      )}
    >
      {renderContent()}
    </div>
  );
};

export default ObservationFormatter;
