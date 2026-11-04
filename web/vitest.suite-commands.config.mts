import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: { alias: { '@': fileURLToPath(new URL('.', import.meta.url)) } },
  oxc: { jsx: { runtime: 'automatic' } },
  test: {
    environment: 'jsdom',
    include: [
      './utils/suite-commands.test.ts',
      './utils/suite-command-inputs.test.ts',
      './new-components/chat/input/SuiteCommandPopover.test.tsx',
    ],
    restoreMocks: true,
    clearMocks: true,
  },
});
