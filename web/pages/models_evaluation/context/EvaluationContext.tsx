import React, { createContext, useContext, useState } from 'react';
import { useEvaluationList } from '../hooks/useEvaluationList';

interface EvaluationContextType {
  refresh: () => void;
  data: any;
  loading: boolean;
  getModelsEvaluation: (page?: number, pageSize?: number) => void;
}

const EvaluationContext = createContext<EvaluationContextType | undefined>(undefined);

interface EvaluationProviderProps {
  children: React.ReactNode;
  filterValue?: string;
  type?: string;
}

export const EvaluationProvider: React.FC<EvaluationProviderProps> = ({
  children, 
  filterValue = '', 
  type = 'all' 
}) => {
  const {
    data,
    loading,
    getModelsEvaluation,
    refresh,
  } = useEvaluationList({
    filterValue,
    type,
  });

  return (
    <EvaluationContext.Provider
      value={{
        refresh, 
        data,
        loading, 
        getModelsEvaluation
      }}
    >
      {children}
    </EvaluationContext.Provider>
  );
};

export const useEvaluation = () => {
  const context = useContext(EvaluationContext);
  if (context === undefined) {
    throw new Error('useEvaluation must be used within an EvaluationProvider');
  }
  return context;
};

interface EvaluationItemContextType {
  data: {
    name: string;
    id: string,
    createTime: string;
    modifiedTime: string;
  },
  setData: (data: EvaluationItemContextType['data']) => void;
}

interface EvaluationItemProviderProps {
  children: React.ReactNode;
}

export const EvaluationItemContext = createContext<EvaluationItemContextType | undefined>(undefined);

export const EvaluationItemProvider: React.FC<EvaluationItemProviderProps> = ({
  children
}) => {

  const [data, setData] = useState({
    name: '',
    id: '',
    createTime: '',
    modifiedTime: '',
  })

  return (
    <EvaluationItemContext.Provider
      value={{
        data,
        setData,
      }}
    >
      {children}
    </EvaluationItemContext.Provider>
  )
}

export const useEvaluationItem = () => {
  const context = useContext(EvaluationItemContext);
  if (context === undefined) {
    throw new Error('useEvaluationItem must be used within an EvaluationItemProvider');
  }
  return context;
}