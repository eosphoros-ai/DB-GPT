import React, { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
};

type State = { error: Error | null };

/** Catches render errors in heavy panels (charts, markdown, image preview). */
export default class ClientErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ClientErrorBoundary:', error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        this.props.fallback ?? (
          <div className='rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-800 dark:bg-amber-900/20 px-4 py-3 text-sm text-amber-800 dark:text-amber-200'>
            Не удалось отобразить блок. Попробуйте другой шаг или обновите страницу (Ctrl+Shift+R).
          </div>
        )
      );
    }
    return this.props.children;
  }
}
