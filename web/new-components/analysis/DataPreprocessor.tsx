/**
 * DataPreprocessor.tsx
 * Advanced data preprocessing component with auto type detection, missing value handling,
 * outlier processing, and data normalization/scaling.
 */

import {
  AlertOutlined,
  CheckCircleOutlined,
  EditOutlined,
  EyeOutlined,
  FilterOutlined,
  ReloadOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Divider,
  Modal,
  Progress,
  Radio,
  Select,
  Statistic,
  Switch,
  Table,
  Tabs,
  Tag,
} from 'antd';
import React, { useCallback, useEffect, useMemo, useState } from 'react';

export type ColumnType = 'number' | 'string' | 'date' | 'boolean' | 'category' | 'mixed' | 'unknown';

export type MissingValueStrategy =
  | 'drop'
  | 'fill_mean'
  | 'fill_median'
  | 'fill_mode'
  | 'fill_zero'
  | 'fill_custom'
  | 'interpolate'
  | 'keep';

export type OutlierStrategy = 'keep' | 'remove' | 'cap' | 'flag';

export type NormalizationMethod = 'none' | 'minmax' | 'zscore' | 'log' | 'robust';

export interface ColumnConfig {
  name: string;
  detectedType: ColumnType;
  selectedType: ColumnType;
  missingCount: number;
  missingPercent: number;
  missingStrategy: MissingValueStrategy;
  customFillValue?: any;
  outlierCount: number;
  outlierStrategy: OutlierStrategy;
  outlierThreshold: number;
  normalization: NormalizationMethod;
  include: boolean;
  uniqueValues: number;
  sampleValues: any[];
}

export interface PreprocessingConfig {
  columns: ColumnConfig[];
  globalMissingStrategy: MissingValueStrategy;
  globalOutlierStrategy: OutlierStrategy;
  dropDuplicates: boolean;
  trimWhitespace: boolean;
  lowercaseStrings: boolean;
  removeEmptyRows: boolean;
}

export interface PreprocessingResult {
  originalRowCount: number;
  processedRowCount: number;
  columnsProcessed: number;
  missingValuesFilled: number;
  outliersHandled: number;
  duplicatesRemoved: number;
  data: any[];
  warnings: string[];
  errors: string[];
}

const detectColumnType = (values: any[]): ColumnType => {
  const nonNullValues = values.filter(v => v != null && v !== '');
  if (nonNullValues.length === 0) return 'unknown';

  let numberCount = 0;
  let dateCount = 0;
  let boolCount = 0;
  let stringCount = 0;

  for (const val of nonNullValues) {
    if (typeof val === 'boolean' || val === 'true' || val === 'false' || val === '0' || val === '1') {
      boolCount++;
    } else if (!isNaN(Number(val)) && val !== '') {
      numberCount++;
    } else if (!isNaN(Date.parse(String(val))) && /\d{4}|\d{2}[-/]\d{2}/.test(String(val))) {
      dateCount++;
    } else {
      stringCount++;
    }
  }

  const total = nonNullValues.length;
  const threshold = 0.8;

  if (numberCount / total >= threshold) return 'number';
  if (dateCount / total >= threshold) return 'date';
  if (boolCount / total >= threshold) return 'boolean';
  if (stringCount / total >= threshold) {
    const uniqueRatio = new Set(nonNullValues).size / total;
    if (uniqueRatio < 0.3 && total > 10) return 'category';
    return 'string';
  }

  return 'mixed';
};

const calculateMissing = (values: any[]): { count: number; percent: number } => {
  const missing = values.filter(v => v == null || v === '' || (typeof v === 'number' && isNaN(v))).length;
  return {
    count: missing,
    percent: values.length > 0 ? (missing / values.length) * 100 : 0,
  };
};

const detectOutliers = (values: number[], threshold: number = 3): number[] => {
  const numericValues = values.filter(v => typeof v === 'number' && !isNaN(v));
  if (numericValues.length < 3) return [];

  const mean = numericValues.reduce((a, b) => a + b, 0) / numericValues.length;
  const variance = numericValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / numericValues.length;
  const stdDev = Math.sqrt(variance);

  if (stdDev === 0) return [];

  const outlierIndices: number[] = [];
  values.forEach((v, i) => {
    if (typeof v === 'number' && !isNaN(v)) {
      const zScore = Math.abs((v - mean) / stdDev);
      if (zScore > threshold) {
        outlierIndices.push(i);
      }
    }
  });

  return outlierIndices;
};

const getSampleValues = (values: any[], count: number = 5): any[] => {
  const unique = [...new Set(values.filter(v => v != null && v !== ''))];
  return unique.slice(0, count);
};

export const analyzeColumns = (data: any[], columns: string[]): ColumnConfig[] => {
  return columns.map(colName => {
    const values = data.map(row => row[colName]);
    const detectedType = detectColumnType(values);
    const { count: missingCount, percent: missingPercent } = calculateMissing(values);

    let outlierCount = 0;
    if (detectedType === 'number') {
      const numericValues = values.map(v => (v != null && v !== '' ? Number(v) : NaN));
      outlierCount = detectOutliers(numericValues).length;
    }

    return {
      name: colName,
      detectedType,
      selectedType: detectedType,
      missingCount,
      missingPercent,
      missingStrategy: missingPercent > 50 ? 'drop' : missingPercent > 0 ? 'fill_mean' : 'keep',
      outlierCount,
      outlierStrategy: 'keep',
      outlierThreshold: 3,
      normalization: 'none',
      include: true,
      uniqueValues: new Set(values.filter(v => v != null)).size,
      sampleValues: getSampleValues(values),
    };
  });
};

const fillMissingValues = (values: any[], strategy: MissingValueStrategy, customValue?: any): any[] => {
  if (strategy === 'keep') return values;

  const nonNull = values.filter(v => v != null && v !== '' && !(typeof v === 'number' && isNaN(v)));

  let fillValue: any = null;
  switch (strategy) {
    case 'fill_mean':
      const nums = nonNull.filter(v => !isNaN(Number(v))).map(Number);
      fillValue = nums.length > 0 ? nums.reduce((a, b) => a + b, 0) / nums.length : 0;
      break;
    case 'fill_median':
      const sorted = nonNull
        .filter(v => !isNaN(Number(v)))
        .map(Number)
        .sort((a, b) => a - b);
      fillValue = sorted.length > 0 ? sorted[Math.floor(sorted.length / 2)] : 0;
      break;
    case 'fill_mode':
      const frequency: Record<string, number> = {};
      nonNull.forEach(v => {
        frequency[String(v)] = (frequency[String(v)] || 0) + 1;
      });
      const maxFreq = Math.max(...Object.values(frequency));
      fillValue = Object.keys(frequency).find(k => frequency[k] === maxFreq) || '';
      break;
    case 'fill_zero':
      fillValue = 0;
      break;
    case 'fill_custom':
      fillValue = customValue;
      break;
    case 'interpolate':
      return values.map((v, i) => {
        if (v == null || v === '' || (typeof v === 'number' && isNaN(v))) {
          let prev = null,
            next = null;
          for (let j = i - 1; j >= 0; j--) {
            if (values[j] != null && !isNaN(Number(values[j]))) {
              prev = Number(values[j]);
              break;
            }
          }
          for (let j = i + 1; j < values.length; j++) {
            if (values[j] != null && !isNaN(Number(values[j]))) {
              next = Number(values[j]);
              break;
            }
          }
          if (prev !== null && next !== null) return (prev + next) / 2;
          return prev ?? next ?? 0;
        }
        return v;
      });
    case 'drop':
      return values;
  }

  return values.map(v => (v == null || v === '' || (typeof v === 'number' && isNaN(v)) ? fillValue : v));
};

const handleOutliers = (
  values: number[],
  strategy: OutlierStrategy,
  threshold: number = 3,
): { values: number[]; handled: number } => {
  if (strategy === 'keep') return { values, handled: 0 };

  const numericValues = values.filter(v => typeof v === 'number' && !isNaN(v));
  if (numericValues.length < 3) return { values, handled: 0 };

  const mean = numericValues.reduce((a, b) => a + b, 0) / numericValues.length;
  const variance = numericValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / numericValues.length;
  const stdDev = Math.sqrt(variance);

  if (stdDev === 0) return { values, handled: 0 };

  const lowerBound = mean - threshold * stdDev;
  const upperBound = mean + threshold * stdDev;

  let handled = 0;
  const result = values.map(v => {
    if (typeof v !== 'number' || isNaN(v)) return v;

    if (v < lowerBound || v > upperBound) {
      handled++;
      switch (strategy) {
        case 'cap':
          return v < lowerBound ? lowerBound : upperBound;
        case 'remove':
          return NaN;
        case 'flag':
          return v;
        default:
          return v;
      }
    }
    return v;
  });

  return { values: result, handled };
};

const normalizeValues = (values: number[], method: NormalizationMethod): number[] => {
  if (method === 'none') return values;

  const numericValues = values.filter(v => typeof v === 'number' && !isNaN(v));
  if (numericValues.length === 0) return values;

  switch (method) {
    case 'minmax': {
      const min = Math.min(...numericValues);
      const max = Math.max(...numericValues);
      const range = max - min;
      if (range === 0) return values.map(() => 0);
      return values.map(v => (typeof v === 'number' && !isNaN(v) ? (v - min) / range : v));
    }
    case 'zscore': {
      const mean = numericValues.reduce((a, b) => a + b, 0) / numericValues.length;
      const variance = numericValues.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / numericValues.length;
      const stdDev = Math.sqrt(variance);
      if (stdDev === 0) return values.map(() => 0);
      return values.map(v => (typeof v === 'number' && !isNaN(v) ? (v - mean) / stdDev : v));
    }
    case 'log': {
      return values.map(v => (typeof v === 'number' && !isNaN(v) && v > 0 ? Math.log(v) : v));
    }
    case 'robust': {
      const sorted = [...numericValues].sort((a, b) => a - b);
      const q1 = sorted[Math.floor(sorted.length * 0.25)];
      const q3 = sorted[Math.floor(sorted.length * 0.75)];
      const median = sorted[Math.floor(sorted.length * 0.5)];
      const iqr = q3 - q1;
      if (iqr === 0) return values.map(() => 0);
      return values.map(v => (typeof v === 'number' && !isNaN(v) ? (v - median) / iqr : v));
    }
    default:
      return values;
  }
};

export const preprocessData = (data: any[], config: PreprocessingConfig): PreprocessingResult => {
  const warnings: string[] = [];
  const errors: string[] = [];
  let processedData = [...data.map(row => ({ ...row }))];

  const originalRowCount = processedData.length;
  let missingValuesFilled = 0;
  let outliersHandled = 0;
  let duplicatesRemoved = 0;

  if (config.trimWhitespace) {
    processedData = processedData.map(row => {
      const newRow = { ...row };
      Object.keys(newRow).forEach(key => {
        if (typeof newRow[key] === 'string') {
          newRow[key] = newRow[key].trim();
        }
      });
      return newRow;
    });
  }

  if (config.lowercaseStrings) {
    config.columns
      .filter(c => c.selectedType === 'string' && c.include)
      .forEach(colConfig => {
        processedData.forEach(row => {
          if (typeof row[colConfig.name] === 'string') {
            row[colConfig.name] = row[colConfig.name].toLowerCase();
          }
        });
      });
  }

  const includedColumns = config.columns.filter(c => c.include);
  const dropColumns = config.columns.filter(c => !c.include).map(c => c.name);

  processedData = processedData.map(row => {
    const newRow = { ...row };
    dropColumns.forEach(col => delete newRow[col]);
    return newRow;
  });

  for (const colConfig of includedColumns) {
    const values = processedData.map(row => row[colConfig.name]);

    if (colConfig.missingStrategy !== 'keep') {
      const filled = fillMissingValues(values, colConfig.missingStrategy, colConfig.customFillValue);
      const filledCount = values.filter(
        (v, i) => (v == null || v === '') && filled[i] != null && filled[i] !== '',
      ).length;
      missingValuesFilled += filledCount;

      if (colConfig.missingStrategy === 'drop') {
        const indicesToRemove = new Set<number>();
        values.forEach((v, i) => {
          if (v == null || v === '' || (typeof v === 'number' && isNaN(v))) {
            indicesToRemove.add(i);
          }
        });
        processedData = processedData.filter((_, i) => !indicesToRemove.has(i));
      } else {
        filled.forEach((v, i) => {
          if (processedData[i]) {
            processedData[i][colConfig.name] = v;
          }
        });
      }
    }

    if (colConfig.selectedType === 'number' && colConfig.outlierStrategy !== 'keep') {
      const currentValues = processedData.map(row => Number(row[colConfig.name]));
      const { values: handledValues, handled } = handleOutliers(
        currentValues,
        colConfig.outlierStrategy,
        colConfig.outlierThreshold,
      );
      outliersHandled += handled;

      if (colConfig.outlierStrategy === 'remove') {
        processedData = processedData.filter((_, i) => !isNaN(handledValues[i]));
      } else {
        handledValues.forEach((v, i) => {
          if (processedData[i]) {
            processedData[i][colConfig.name] = v;
          }
        });
      }
    }

    if (colConfig.selectedType === 'number' && colConfig.normalization !== 'none') {
      const currentValues = processedData.map(row => Number(row[colConfig.name]));
      const normalized = normalizeValues(currentValues, colConfig.normalization);
      normalized.forEach((v, i) => {
        if (processedData[i]) {
          processedData[i][colConfig.name] = v;
        }
      });
    }
  }

  if (config.dropDuplicates) {
    const seen = new Set<string>();
    const uniqueData: any[] = [];
    processedData.forEach(row => {
      const key = JSON.stringify(row);
      if (!seen.has(key)) {
        seen.add(key);
        uniqueData.push(row);
      }
    });
    duplicatesRemoved = processedData.length - uniqueData.length;
    processedData = uniqueData;
  }

  if (config.removeEmptyRows) {
    const beforeCount = processedData.length;
    processedData = processedData.filter(row => Object.values(row).some(v => v != null && v !== ''));
    if (beforeCount > processedData.length) {
      warnings.push(`Removed ${beforeCount - processedData.length} empty rows`);
    }
  }

  return {
    originalRowCount,
    processedRowCount: processedData.length,
    columnsProcessed: includedColumns.length,
    missingValuesFilled,
    outliersHandled,
    duplicatesRemoved,
    data: processedData,
    warnings,
    errors,
  };
};

interface DataPreprocessorProps {
  data: any[];
  columns: string[];
  onPreprocess: (result: PreprocessingResult) => void;
  onConfigChange?: (config: PreprocessingConfig) => void;
  initialConfig?: Partial<PreprocessingConfig>;
}

const DataPreprocessor: React.FC<DataPreprocessorProps> = ({
  data,
  columns,
  onPreprocess,
  onConfigChange,
  initialConfig,
}) => {
  const [config, setConfig] = useState<PreprocessingConfig>(() => {
    const columnConfigs = analyzeColumns(data, columns);
    return {
      columns: columnConfigs,
      globalMissingStrategy: 'fill_mean',
      globalOutlierStrategy: 'keep',
      dropDuplicates: false,
      trimWhitespace: true,
      lowercaseStrings: false,
      removeEmptyRows: true,
      ...initialConfig,
    };
  });

  const [previewResult, setPreviewResult] = useState<PreprocessingResult | null>(null);
  const [showPreview, setShowPreview] = useState(false);
  const [activeTab, setActiveTab] = useState('columns');

  useEffect(() => {
    onConfigChange?.(config);
  }, [config, onConfigChange]);

  const updateColumnConfig = useCallback((columnName: string, updates: Partial<ColumnConfig>) => {
    setConfig(prev => ({
      ...prev,
      columns: prev.columns.map(col => (col.name === columnName ? { ...col, ...updates } : col)),
    }));
  }, []);

  const applyGlobalStrategy = useCallback((type: 'missing' | 'outlier') => {
    setConfig(prev => ({
      ...prev,
      columns: prev.columns.map(col => ({
        ...col,
        ...(type === 'missing'
          ? { missingStrategy: prev.globalMissingStrategy }
          : { outlierStrategy: prev.globalOutlierStrategy }),
      })),
    }));
  }, []);

  const handlePreview = useCallback(() => {
    const result = preprocessData(data, config);
    setPreviewResult(result);
    setShowPreview(true);
  }, [data, config]);

  const handleApply = useCallback(() => {
    const result = preprocessData(data, config);
    onPreprocess(result);
  }, [data, config, onPreprocess]);

  const dataQualityScore = useMemo(() => {
    const totalMissing = config.columns.reduce((sum, c) => sum + c.missingPercent, 0) / config.columns.length;
    const totalOutliers = config.columns
      .filter(c => c.selectedType === 'number')
      .reduce((sum, c) => sum + c.outlierCount, 0);
    const outlierPercent = data.length > 0 ? (totalOutliers / data.length) * 100 : 0;

    const missingScore = Math.max(0, 100 - totalMissing * 2);
    const outlierScore = Math.max(0, 100 - outlierPercent * 5);
    const typeScore =
      (config.columns.filter(c => c.detectedType !== 'mixed' && c.detectedType !== 'unknown').length /
        config.columns.length) *
      100;

    return Math.round(missingScore * 0.4 + outlierScore * 0.3 + typeScore * 0.3);
  }, [config.columns, data.length]);

  const getTypeIcon = (type: ColumnType) => {
    switch (type) {
      case 'number':
        return '#';
      case 'string':
        return 'Aa';
      case 'date':
        return '📅';
      case 'boolean':
        return '✓';
      case 'category':
        return '📋';
      default:
        return '?';
    }
  };

  const getTypeColor = (type: ColumnType) => {
    switch (type) {
      case 'number':
        return 'blue';
      case 'string':
        return 'green';
      case 'date':
        return 'purple';
      case 'boolean':
        return 'orange';
      case 'category':
        return 'cyan';
      case 'mixed':
        return 'red';
      default:
        return 'default';
    }
  };

  const columnTableColumns = [
    {
      title: 'Column',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: ColumnConfig) => (
        <div className='flex items-center gap-2'>
          <Checkbox checked={record.include} onChange={e => updateColumnConfig(name, { include: e.target.checked })} />
          <span className='font-medium'>{name}</span>
        </div>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'detectedType',
      key: 'type',
      render: (type: ColumnType, record: ColumnConfig) => (
        <Select
          size='small'
          value={record.selectedType}
          onChange={val => updateColumnConfig(record.name, { selectedType: val })}
          className='w-28'
          options={[
            { value: 'number', label: '# Number' },
            { value: 'string', label: 'Aa String' },
            { value: 'date', label: '📅 Date' },
            { value: 'boolean', label: '✓ Boolean' },
            { value: 'category', label: '📋 Category' },
          ]}
        />
      ),
    },
    {
      title: 'Missing',
      key: 'missing',
      render: (_: any, record: ColumnConfig) => (
        <div className='flex items-center gap-2'>
          {record.missingCount > 0 ? (
            <Tag color='red' icon={<WarningOutlined />}>
              {record.missingCount} ({record.missingPercent.toFixed(1)}%)
            </Tag>
          ) : (
            <Tag color='green' icon={<CheckCircleOutlined />}>
              Clean
            </Tag>
          )}
        </div>
      ),
    },
    {
      title: 'Missing Strategy',
      key: 'missingStrategy',
      render: (_: any, record: ColumnConfig) => (
        <Select
          size='small'
          value={record.missingStrategy}
          onChange={val => updateColumnConfig(record.name, { missingStrategy: val })}
          className='w-32'
          disabled={record.missingCount === 0}
          options={[
            { value: 'keep', label: 'Keep as is' },
            { value: 'drop', label: 'Drop rows' },
            { value: 'fill_mean', label: 'Fill mean' },
            { value: 'fill_median', label: 'Fill median' },
            { value: 'fill_mode', label: 'Fill mode' },
            { value: 'fill_zero', label: 'Fill zero' },
            { value: 'interpolate', label: 'Interpolate' },
          ]}
        />
      ),
    },
    {
      title: 'Outliers',
      key: 'outliers',
      render: (_: any, record: ColumnConfig) =>
        record.selectedType === 'number' ? (
          record.outlierCount > 0 ? (
            <Tag color='orange' icon={<AlertOutlined />}>
              {record.outlierCount}
            </Tag>
          ) : (
            <Tag color='green'>None</Tag>
          )
        ) : (
          <span className='text-gray-400'>N/A</span>
        ),
    },
    {
      title: 'Normalize',
      key: 'normalization',
      render: (_: any, record: ColumnConfig) =>
        record.selectedType === 'number' ? (
          <Select
            size='small'
            value={record.normalization}
            onChange={val => updateColumnConfig(record.name, { normalization: val })}
            className='w-28'
            options={[
              { value: 'none', label: 'None' },
              { value: 'minmax', label: 'Min-Max' },
              { value: 'zscore', label: 'Z-Score' },
              { value: 'log', label: 'Log' },
              { value: 'robust', label: 'Robust' },
            ]}
          />
        ) : (
          <span className='text-gray-400'>N/A</span>
        ),
    },
  ];

  return (
    <div className='data-preprocessor space-y-4'>
      <div className='flex items-center justify-between'>
        <div>
          <h3 className='text-lg font-semibold text-gray-800 dark:text-gray-200 flex items-center gap-2'>
            <SettingOutlined />
            Data Preprocessing
          </h3>
          <p className='text-sm text-gray-500 dark:text-gray-400 mt-1'>
            Configure data cleaning and transformation options
          </p>
        </div>
        <div className='flex items-center gap-3'>
          <div className='text-center'>
            <div className='text-2xl font-bold text-blue-600'>{dataQualityScore}</div>
            <div className='text-xs text-gray-500'>Quality Score</div>
          </div>
          <Progress
            type='circle'
            percent={dataQualityScore}
            size={48}
            strokeColor={dataQualityScore >= 80 ? '#10B981' : dataQualityScore >= 60 ? '#F59E0B' : '#EF4444'}
          />
        </div>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'columns',
            label: (
              <span className='flex items-center gap-1.5'>
                <EditOutlined className='text-xs' />
                Column Settings
              </span>
            ),
            children: (
              <div className='space-y-4'>
                <div className='flex items-center justify-between bg-gray-50 dark:bg-gray-800 rounded-lg p-3'>
                  <div className='flex items-center gap-4'>
                    <span className='text-sm text-gray-600 dark:text-gray-400'>Apply to all:</span>
                    <Select
                      size='small'
                      value={config.globalMissingStrategy}
                      onChange={val => setConfig(prev => ({ ...prev, globalMissingStrategy: val }))}
                      className='w-32'
                      options={[
                        { value: 'keep', label: 'Keep missing' },
                        { value: 'fill_mean', label: 'Fill mean' },
                        { value: 'fill_median', label: 'Fill median' },
                        { value: 'drop', label: 'Drop rows' },
                      ]}
                    />
                    <Button size='small' onClick={() => applyGlobalStrategy('missing')}>
                      Apply Missing
                    </Button>
                  </div>
                  <div className='flex items-center gap-2'>
                    <Badge count={config.columns.filter(c => c.include).length} overflowCount={99}>
                      <Tag>Selected Columns</Tag>
                    </Badge>
                  </div>
                </div>

                <Table
                  columns={columnTableColumns}
                  dataSource={config.columns}
                  rowKey='name'
                  size='small'
                  pagination={false}
                  scroll={{ y: 300 }}
                />
              </div>
            ),
          },
          {
            key: 'options',
            label: (
              <span className='flex items-center gap-1.5'>
                <FilterOutlined className='text-xs' />
                Global Options
              </span>
            ),
            children: (
              <div className='grid grid-cols-2 gap-6 p-4'>
                <Card size='small' title='Text Processing' className='shadow-sm'>
                  <div className='space-y-3'>
                    <div className='flex items-center justify-between'>
                      <span className='text-sm'>Trim whitespace</span>
                      <Switch
                        checked={config.trimWhitespace}
                        onChange={val => setConfig(prev => ({ ...prev, trimWhitespace: val }))}
                      />
                    </div>
                    <div className='flex items-center justify-between'>
                      <span className='text-sm'>Lowercase strings</span>
                      <Switch
                        checked={config.lowercaseStrings}
                        onChange={val => setConfig(prev => ({ ...prev, lowercaseStrings: val }))}
                      />
                    </div>
                  </div>
                </Card>

                <Card size='small' title='Row Processing' className='shadow-sm'>
                  <div className='space-y-3'>
                    <div className='flex items-center justify-between'>
                      <span className='text-sm'>Remove duplicates</span>
                      <Switch
                        checked={config.dropDuplicates}
                        onChange={val => setConfig(prev => ({ ...prev, dropDuplicates: val }))}
                      />
                    </div>
                    <div className='flex items-center justify-between'>
                      <span className='text-sm'>Remove empty rows</span>
                      <Switch
                        checked={config.removeEmptyRows}
                        onChange={val => setConfig(prev => ({ ...prev, removeEmptyRows: val }))}
                      />
                    </div>
                  </div>
                </Card>

                <Card size='small' title='Outlier Handling' className='shadow-sm col-span-2'>
                  <div className='space-y-3'>
                    <div className='flex items-center gap-4'>
                      <span className='text-sm text-gray-600'>Global strategy:</span>
                      <Radio.Group
                        value={config.globalOutlierStrategy}
                        onChange={e => setConfig(prev => ({ ...prev, globalOutlierStrategy: e.target.value }))}
                        size='small'
                      >
                        <Radio.Button value='keep'>Keep</Radio.Button>
                        <Radio.Button value='cap'>Cap</Radio.Button>
                        <Radio.Button value='remove'>Remove</Radio.Button>
                        <Radio.Button value='flag'>Flag</Radio.Button>
                      </Radio.Group>
                      <Button size='small' onClick={() => applyGlobalStrategy('outlier')}>
                        Apply to All
                      </Button>
                    </div>
                  </div>
                </Card>
              </div>
            ),
          },
          {
            key: 'summary',
            label: (
              <span className='flex items-center gap-1.5'>
                <ThunderboltOutlined className='text-xs' />
                Summary
              </span>
            ),
            children: (
              <div className='grid grid-cols-4 gap-4 p-4'>
                <Card size='small' className='text-center'>
                  <Statistic title='Total Rows' value={data.length} valueStyle={{ color: '#3B82F6' }} />
                </Card>
                <Card size='small' className='text-center'>
                  <Statistic title='Total Columns' value={columns.length} valueStyle={{ color: '#10B981' }} />
                </Card>
                <Card size='small' className='text-center'>
                  <Statistic
                    title='Missing Values'
                    value={config.columns.reduce((sum, c) => sum + c.missingCount, 0)}
                    valueStyle={{ color: '#F59E0B' }}
                    prefix={<WarningOutlined />}
                  />
                </Card>
                <Card size='small' className='text-center'>
                  <Statistic
                    title='Outliers Detected'
                    value={config.columns
                      .filter(c => c.selectedType === 'number')
                      .reduce((sum, c) => sum + c.outlierCount, 0)}
                    valueStyle={{ color: '#EF4444' }}
                    prefix={<AlertOutlined />}
                  />
                </Card>

                <div className='col-span-4'>
                  <h4 className='text-sm font-semibold mb-2 text-gray-700 dark:text-gray-300'>
                    Column Type Distribution
                  </h4>
                  <div className='flex flex-wrap gap-2'>
                    {['number', 'string', 'date', 'boolean', 'category', 'mixed', 'unknown'].map(type => {
                      const count = config.columns.filter(c => c.detectedType === type).length;
                      if (count === 0) return null;
                      return (
                        <Tag key={type} color={getTypeColor(type as ColumnType)}>
                          {getTypeIcon(type as ColumnType)} {type}: {count}
                        </Tag>
                      );
                    })}
                  </div>
                </div>
              </div>
            ),
          },
        ]}
      />

      <Divider className='my-4' />

      <div className='flex items-center justify-between'>
        <div className='flex items-center gap-2'>
          <Button
            icon={<ReloadOutlined />}
            onClick={() => setConfig(prev => ({ ...prev, columns: analyzeColumns(data, columns) }))}
          >
            Reset
          </Button>
        </div>
        <div className='flex items-center gap-2'>
          <Button icon={<EyeOutlined />} onClick={handlePreview}>
            Preview
          </Button>
          <Button type='primary' icon={<ThunderboltOutlined />} onClick={handleApply}>
            Apply Preprocessing
          </Button>
        </div>
      </div>

      <Modal
        title='Preview Preprocessing Results'
        open={showPreview}
        onCancel={() => setShowPreview(false)}
        width={800}
        footer={[
          <Button key='close' onClick={() => setShowPreview(false)}>
            Close
          </Button>,
          <Button
            key='apply'
            type='primary'
            onClick={() => {
              if (previewResult) {
                onPreprocess(previewResult);
                setShowPreview(false);
              }
            }}
          >
            Apply Changes
          </Button>,
        ]}
      >
        {previewResult && (
          <div className='space-y-4'>
            <div className='grid grid-cols-3 gap-4'>
              <Card size='small'>
                <Statistic
                  title='Rows'
                  value={previewResult.processedRowCount}
                  suffix={`/ ${previewResult.originalRowCount}`}
                  valueStyle={{
                    color: previewResult.processedRowCount < previewResult.originalRowCount ? '#F59E0B' : '#10B981',
                  }}
                />
              </Card>
              <Card size='small'>
                <Statistic
                  title='Missing Filled'
                  value={previewResult.missingValuesFilled}
                  valueStyle={{ color: '#3B82F6' }}
                />
              </Card>
              <Card size='small'>
                <Statistic
                  title='Outliers Handled'
                  value={previewResult.outliersHandled}
                  valueStyle={{ color: '#8B5CF6' }}
                />
              </Card>
            </div>

            {previewResult.warnings.length > 0 && (
              <Alert
                type='warning'
                message='Warnings'
                description={
                  <ul className='list-disc pl-4'>
                    {previewResult.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                }
                showIcon
              />
            )}

            <div className='border rounded-lg overflow-hidden'>
              <Table
                columns={Object.keys(previewResult.data[0] || {}).map(key => ({
                  title: key,
                  dataIndex: key,
                  key,
                  ellipsis: true,
                  width: 120,
                }))}
                dataSource={previewResult.data.slice(0, 10)}
                rowKey={(_, i) => String(i)}
                size='small'
                pagination={false}
                scroll={{ x: true }}
              />
              {previewResult.data.length > 10 && (
                <div className='text-center py-2 text-sm text-gray-500'>
                  Showing first 10 of {previewResult.data.length} rows
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default DataPreprocessor;
