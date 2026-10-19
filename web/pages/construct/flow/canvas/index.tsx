import { useRouter } from 'next/router';
import { useEffect } from 'react';

/**
 * @deprecated The legacy AWEL flow UI has been replaced by the TaskFlow
 * product (/construct/taskflow + /taskflow/editor). Redirect old links.
 */
export default function LegacyFlowRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/construct/taskflow');
  }, [router]);
  return null;
}
