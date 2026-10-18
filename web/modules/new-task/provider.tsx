/** React facade for the app-wide new-task command. */

import { useRouter } from 'next/router';
import React, { createContext, useCallback, useContext, useEffect, useRef } from 'react';

import type { NewTaskCoordinator, NewTaskGuard } from './coordinator';
import { createNewTaskCoordinator } from './coordinator';

const NewTaskContext = createContext<NewTaskCoordinator | null>(null);

function useCoordinator(): NewTaskCoordinator {
  const coordinator = useContext(NewTaskContext);
  if (!coordinator) {
    throw new Error('New-task hooks must be used within NewTaskProvider.');
  }
  return coordinator;
}

export function NewTaskProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const routerRef = useRef(router);
  routerRef.current = router;

  const coordinatorRef = useRef<NewTaskCoordinator | null>(null);
  if (!coordinatorRef.current) {
    coordinatorRef.current = createNewTaskCoordinator({
      isCanonicalHome: () => {
        const current = routerRef.current;
        return current.pathname === '/' && current.asPath === '/';
      },
      goCanonicalHome: async () => {
        const current = routerRef.current;
        await current.replace('/', undefined, { shallow: current.pathname === '/' });
      },
    });
  }

  return <NewTaskContext.Provider value={coordinatorRef.current}>{children}</NewTaskContext.Provider>;
}

/** Return the single app-wide command used by every "new task" affordance. */
export function useStartNewTask(): () => Promise<void> {
  const coordinator = useCoordinator();
  return useCallback(() => coordinator.begin(), [coordinator]);
}

/** Attach the mounted task workspace that owns the reset implementation. */
export function useNewTaskOwner(resetForNewTask: () => void): void {
  const coordinator = useCoordinator();
  const resetRef = useRef(resetForNewTask);
  resetRef.current = resetForNewTask;

  useEffect(() => coordinator.attach(() => resetRef.current()), [coordinator]);
}

/**
 * Attach a guard consulted before every command. Resolve false to cancel the
 * command (e.g. while a turn is in flight and the user declines the
 * interruption confirmation).
 */
export function useNewTaskGuard(guard: NewTaskGuard): void {
  const coordinator = useCoordinator();
  const guardRef = useRef(guard);
  guardRef.current = guard;

  useEffect(() => coordinator.attachGuard(() => guardRef.current()), [coordinator]);
}
