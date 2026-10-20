import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('.', import.meta.url)),
    },
  },
  oxc: {
    jsx: {
      runtime: 'automatic',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./new-components/dashboard/test-setup.ts'],
    include: [
      './new-components/dashboard/**/*.test.{ts,tsx}',
      './new-components/scheduled-task/**/*.test.{ts,tsx}',
      './hooks/use-scheduled-task.test.tsx',
      './new-components/chat/content/QuestionDock.test.tsx',
      './hooks/use-question-session.test.tsx',
      './hooks/use-chat.question.test.tsx',
      './hooks/use-chat.failure.test.tsx',
      './utils/question-session.test.ts',
      './lib/model-runtime.test.ts',
    ],
    restoreMocks: true,
    clearMocks: true,
    // Ant Design components can take more than Vitest's 5s default to
    // initialise when the local DB-GPT frontend and backend are running in
    // parallel on Windows. Keep the limit finite while avoiding false CI/UAT
    // failures caused only by machine load.
    testTimeout: 15_000,
  },
});
