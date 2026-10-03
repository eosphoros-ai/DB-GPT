import nextVitals from 'eslint-config-next/core-web-vitals';
import nextTypeScript from 'eslint-config-next/typescript';
import prettier from 'eslint-config-prettier/flat';
import { defineConfig, globalIgnores } from 'eslint/config';

// Preserve the two hook checks enabled by the previous configuration. Enabling
// React Compiler's additional checks requires a separate application-wide audit;
// the compiler itself is not enabled by this tooling migration.
const legacyHookRules = new Set(['react-hooks/rules-of-hooks', 'react-hooks/exhaustive-deps']);
const compatibleNextVitals = nextVitals.map(config => ({
  ...config,
  ...(config.rules
    ? {
        rules: Object.fromEntries(
          Object.entries(config.rules).filter(
            ([name]) => !name.startsWith('react-hooks/') || legacyHookRules.has(name),
          ),
        ),
      }
    : {}),
}));

export default defineConfig([
  ...compatibleNextVitals,
  ...nextTypeScript,
  {
    rules: {
      'react/prop-types': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-expressions': ['error', { allowShortCircuit: true, allowTernary: true }],
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          args: 'all',
          argsIgnorePattern: '^_',
          caughtErrors: 'all',
          caughtErrorsIgnorePattern: '^_',
          destructuredArrayIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          ignoreRestSiblings: true,
        },
      ],
    },
  },
  {
    // Node build scripts and next.config.js intentionally use CommonJS.
    files: ['**/*.cjs', 'next.config.js', 'tailwind.config.js'],
    rules: { '@typescript-eslint/no-require-imports': 'off' },
  },
  prettier,
  globalIgnores(['.next*/**', 'out/**', 'build/**', 'dist/**', 'node_modules/**', 'next-env.d.ts']),
]);
