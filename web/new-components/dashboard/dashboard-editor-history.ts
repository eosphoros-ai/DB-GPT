import { DashboardSchemaV1 } from '@/types/dashboard';
import { Dispatch, SetStateAction, useCallback, useReducer } from 'react';

export interface DashboardHistoryState {
  past: DashboardSchemaV1[];
  present: DashboardSchemaV1;
  future: DashboardSchemaV1[];
}

type DashboardHistoryAction =
  | { type: 'set'; update: SetStateAction<DashboardSchemaV1> }
  | { type: 'reset'; schema: DashboardSchemaV1 }
  | { type: 'saved'; submitted: DashboardSchemaV1; schema: DashboardSchemaV1 }
  | { type: 'undo' }
  | { type: 'redo' };

const MAX_HISTORY = 50;

export const dashboardHistoryReducer = (
  state: DashboardHistoryState,
  action: DashboardHistoryAction,
): DashboardHistoryState => {
  // A save acknowledges its submitted snapshot, not edits made while it was pending.
  if (action.type === 'saved') {
    if (JSON.stringify(state.present) !== JSON.stringify(action.submitted)) return state;
    // Editing then undoing can return to the submitted snapshot while still
    // leaving newer work in Redo. A save acknowledgement must retain it.
    if (state.future.length) return { ...state, present: action.schema };
    return { past: [], present: action.schema, future: [] };
  }
  if (action.type === 'reset') return { past: [], present: action.schema, future: [] };
  if (action.type === 'undo') {
    const previous = state.past[state.past.length - 1];
    if (!previous) return state;
    return {
      past: state.past.slice(0, -1),
      present: previous,
      future: [state.present, ...state.future].slice(0, MAX_HISTORY),
    };
  }
  if (action.type === 'redo') {
    const next = state.future[0];
    if (!next) return state;
    return {
      past: [...state.past, state.present].slice(-MAX_HISTORY),
      present: next,
      future: state.future.slice(1),
    };
  }
  const next = typeof action.update === 'function' ? action.update(state.present) : action.update;
  if (next === state.present || JSON.stringify(next) === JSON.stringify(state.present)) return state;
  return {
    past: [...state.past, state.present].slice(-MAX_HISTORY),
    present: next,
    future: [],
  };
};

export const useDashboardSchemaHistory = (initialSchema: DashboardSchemaV1) => {
  const [history, dispatch] = useReducer(dashboardHistoryReducer, {
    past: [],
    present: initialSchema,
    future: [],
  });
  const setSchema: Dispatch<SetStateAction<DashboardSchemaV1>> = useCallback(
    update => dispatch({ type: 'set', update }),
    [],
  );
  const resetSchema = useCallback((schema: DashboardSchemaV1) => dispatch({ type: 'reset', schema }), []);
  const acknowledgeSave = useCallback(
    (submitted: DashboardSchemaV1, schema: DashboardSchemaV1) => dispatch({ type: 'saved', submitted, schema }),
    [],
  );
  const undo = useCallback(() => dispatch({ type: 'undo' }), []);
  const redo = useCallback(() => dispatch({ type: 'redo' }), []);
  return {
    schema: history.present,
    setSchema,
    resetSchema,
    acknowledgeSave,
    undo,
    redo,
    canUndo: history.past.length > 0,
    canRedo: history.future.length > 0,
  };
};
