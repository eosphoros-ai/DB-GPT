import { Datum } from '@antv/ava';
import * as XLSX from 'xlsx';

export type ExportFormat = 'excel' | 'csv' | 'json';

export interface ExportOptions {
  data: Datum[];
  fileName?: string;
  format: ExportFormat;
}

/**
 * Generate file name with timestamp if no custom name provided
 * @param extension File extension
 * @param customName Custom file name (optional)
 * @returns Complete file name
 */
export const generateFileName = (extension: string, customName?: string): string => {
  if (customName && customName.trim()) {
    return `${customName.trim()}.${extension}`;
  }
  const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
  return `chat_table_${timestamp}.${extension}`;
};

/**
 * Export data to Excel format
 * @param data Data to export
 * @param customName Custom file name (optional)
 */
export const exportToExcel = (data: Datum[], customName?: string): void => {
  if (!data || data.length === 0) {
    console.warn('No data to export');
    return;
  }

  try {
    const workbook = XLSX.utils.book_new();
    const worksheet = XLSX.utils.json_to_sheet(data);

    // Set column widths
    const columns = data[0] ? Object.keys(data[0]) : [];
    const columnWidths = columns.map(col => ({
      wch: Math.max(col.length, 15),
    }));
    worksheet['!cols'] = columnWidths;

    XLSX.utils.book_append_sheet(workbook, worksheet, 'Data');
    XLSX.writeFile(workbook, generateFileName('xlsx', customName));
  } catch (error) {
    console.error('Export to Excel failed:', error);
    throw new Error('Failed to export Excel file');
  }
};

/**
 * Export data to CSV format
 * @param data Data to export
 * @param customName Custom file name (optional)
 */
export const exportToCSV = (data: Datum[], customName?: string): void => {
  if (!data || data.length === 0) {
    console.warn('No data to export');
    return;
  }

  try {
    const worksheet = XLSX.utils.json_to_sheet(data);
    const csvContent = XLSX.utils.sheet_to_csv(worksheet);

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', generateFileName('csv', customName));
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Export to CSV failed:', error);
    throw new Error('Failed to export CSV file');
  }
};

/**
 * Export data to JSON format
 * @param data Data to export
 * @param customName Custom file name (optional)
 */
export const exportToJSON = (data: Datum[], customName?: string): void => {
  if (!data || data.length === 0) {
    console.warn('No data to export');
    return;
  }

  try {
    const jsonContent = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonContent], { type: 'application/json;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', generateFileName('json', customName));
    link.style.visibility = 'hidden';

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    URL.revokeObjectURL(url);
  } catch (error) {
    console.error('Export to JSON failed:', error);
    throw new Error('Failed to export JSON file');
  }
};

/**
 * Generic export function that handles all formats
 * @param options Export options including data, format, and optional fileName
 */
export const exportData = (options: ExportOptions): void => {
  const { data, fileName, format } = options;

  switch (format) {
    case 'excel':
      exportToExcel(data, fileName);
      break;
    case 'csv':
      exportToCSV(data, fileName);
      break;
    case 'json':
      exportToJSON(data, fileName);
      break;
    default:
      throw new Error(`Unsupported export format: ${format}`);
  }
};
