import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: { alias: { '@': fileURLToPath(new URL('.', import.meta.url)) } },
  oxc: { jsx: { runtime: 'automatic' } },
  test: {
    environment: 'jsdom',
    include: ['./new-components/chat/content/ManusLeftPanel.copy.test.tsx'],
    restoreMocks: true,
    clearMocks: true,
  },
});
