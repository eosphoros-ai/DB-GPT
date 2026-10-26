import React, { createContext, useContext, useMemo } from 'react';
import { indexReport } from './report-data';
import type { FinancialReportData } from './types';

const ReportContext = createContext<(ReturnType<typeof indexReport> & { data: FinancialReportData }) | null>(null);

export const ReportDataProvider: React.FC<React.PropsWithChildren<{ data: FinancialReportData }>> = ({
  data,
  children,
}) => {
  const value = useMemo(() => ({ data, ...indexReport(data) }), [data]);
  return <ReportContext.Provider value={value}>{children}</ReportContext.Provider>;
};

export function useReportData() {
  const value = useContext(ReportContext);
  if (!value) throw new Error('Financial analysis requires a ReportDataProvider');
  return value;
}

export function useSingleReportData() {
  const value = useReportData();
  if (value.data.mode !== 'report') throw new Error('Single report section requires schema version 1');
  return { ...value, data: value.data };
}
