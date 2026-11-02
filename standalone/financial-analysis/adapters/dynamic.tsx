import React, { lazy, Suspense } from 'react';
// Webpack's eager import mode resolves every loader from the same inline bundle.
export default function dynamic(loader: () => Promise<{ default: React.ComponentType<any> }>, options: { loading?: React.ComponentType } = {}) {
  const Component = lazy(loader);
  const Loading = options.loading;
  return function InlineComponent(props: any) {
    return <Suspense fallback={Loading ? <Loading /> : null}><Component {...props} /></Suspense>;
  };
}
