/** Coordinate the explicit "new task" command across the app layout. */

export interface NewTaskNavigation {
  isCanonicalHome: () => boolean;
  goCanonicalHome: () => Promise<void>;
}

/**
 * Runs before the command touches any state. Return/resolve `false` to
 * cancel the command entirely — no reset, no navigation.
 */
export type NewTaskGuard = () => boolean | Promise<boolean>;

export interface NewTaskCoordinator {
  begin: () => Promise<void>;
  attach: (reset: () => void) => () => void;
  attachGuard: (guard: NewTaskGuard) => () => void;
}

export function createNewTaskCoordinator(navigation: NewTaskNavigation): NewTaskCoordinator {
  let target: (() => void) | null = null;
  let guard: NewTaskGuard | null = null;
  let inFlight: Promise<void> | null = null;
  let requestedEpoch = 0;
  let handledEpoch = 0;

  return {
    begin(): Promise<void> {
      if (inFlight) return inFlight;
      const commandEpoch = ++requestedEpoch;
      const runResetAndNavigation = (): Promise<void> | void => {
        if (target) {
          target();
          handledEpoch = commandEpoch;
        }
        if (!navigation.isCanonicalHome()) {
          return navigation.goCanonicalHome();
        }
      };

      let command: Promise<void>;
      if (guard) {
        command = (async () => {
          const allowed = await (guard as NewTaskGuard)();
          if (!allowed) {
            // A cancelled command is consumed: it must not fire on a later
            // attach after the workspace remounts.
            handledEpoch = commandEpoch;
            return;
          }
          await runResetAndNavigation();
        })();
      } else {
        // No guard: keep the command synchronous up to the navigation await,
        // and let a synchronously-throwing owner reject without claiming
        // inFlight — both behaviors existing callers rely on.
        try {
          command = Promise.resolve(runResetAndNavigation());
        } catch (error) {
          return Promise.reject(error);
        }
      }
      inFlight = command;
      const clear = () => {
        if (inFlight === command) inFlight = null;
      };
      void command.then(clear, clear);
      return command;
    },
    attach(reset: () => void): () => void {
      target = reset;
      if (handledEpoch < requestedEpoch) {
        reset();
        handledEpoch = requestedEpoch;
      }
      return () => {
        if (target === reset) {
          target = null;
        }
      };
    },
    attachGuard(newGuard: NewTaskGuard): () => void {
      guard = newGuard;
      return () => {
        if (guard === newGuard) {
          guard = null;
        }
      };
    },
  };
}
