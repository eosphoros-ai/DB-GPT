import { useReducer } from 'react';

const useStateReducer = <T>(initialState: T) => {
  const methods = useReducer(
    (state: T, newState: Partial<T>) => ({
      ...state,
      ...newState,
    }),
    {
      ...initialState,
    }
  );

  return methods;
};

export default useStateReducer;
