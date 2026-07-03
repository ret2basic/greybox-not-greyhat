import eslint from '@eslint/js'
import tseslint from '@typescript-eslint/eslint-plugin'
import tseslintParser from '@typescript-eslint/parser'
import reactPlugin from 'eslint-plugin-react'
import reactHooksPlugin from 'eslint-plugin-react-hooks'
import prettierConfig from 'eslint-config-prettier'
import prettierPlugin from 'eslint-plugin-prettier'
import globals from 'globals'
import nextPlugin from '@next/eslint-plugin-next'

export default [
  {
    ignores: [
      'node_modules/**',
      'dist/**',
      'postcss.config.js',
      'tailwind.config.js',
      'vite.config.ts',
      'commitlint.config.cjs',
      'scripts/validate-commit.cjs',
    ],
  },
  eslint.configs.recommended,
  {
    files: ['server.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.node,
        console: true,
        fetch: true,
        URL: true,
        WebSocket: true,
      },
    },
  },
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      parser: tseslintParser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
        ecmaFeatures: {
          jsx: true,
        },
      },
      globals: {
        ...globals.browser,
        ...globals.node,
        window: true,
        document: true,
        console: true,
        process: true,
        jest: true,
        HTMLElement: true,
        React: true,
        JSX: true,
        HTMLDivElement: true,
      },
    },
    plugins: {
      '@typescript-eslint': tseslint,
      react: reactPlugin,
      'react-hooks': reactHooksPlugin,
      prettier: prettierPlugin,
      '@next/next': nextPlugin,
    },
    rules: {
      ...tseslint.configs.recommended.rules,
      ...reactPlugin.configs.recommended.rules,
      ...reactHooksPlugin.configs.recommended.rules,
      ...prettierConfig.rules,
      ...nextPlugin.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      'react/no-unescaped-entities': 'off',
      'eol-last': 'off',
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
  },
  {
    // Relaxed rules for the relocated "midnight" design-system code. These files
    // were previously under src/components/midnight/** with the same exemption;
    // DAWN-1494 dissolved that folder into the per-feature structure, so the
    // exemption now tracks the files at their new locations. (Tightening these
    // rules is a separate follow-up; this refactor preserves lint behavior.)
    files: [
      'src/components/reserves-projects/**/*.{ts,tsx}',
      'src/components/buy-stake/MidnightBuyForm.tsx',
      'src/components/buy-stake/MidnightStakeForm.tsx',
      'src/components/buy-stake/TokenInput.tsx',
      'src/components/buy-stake/TxOverlay.tsx',
      'src/components/portfolio/MidnightPortfolioPage.tsx',
      'src/components/portfolio/MidnightManageActionsModal.tsx',
      'src/components/portfolio/MidnightWithdrawConfirmModal.tsx',
      'src/components/portfolio/WithdrawAnimation.tsx',
      'src/components/dashboard/BigAreaChart.tsx',
      'src/components/dashboard/ChartModal.tsx',
      'src/components/dashboard/ExpandableCard.tsx',
      'src/components/dashboard/KPIModal.tsx',
      'src/components/dashboard/RangeTabs.tsx',
      'src/components/dashboard/mock-data.ts',
      'src/components/dashboard/utils.ts',
      'src/components/ui/primitives.tsx',
    ],
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unused-vars': 'off',
      '@typescript-eslint/no-unused-expressions': 'off',
      'no-empty': 'off',
    },
  },
]
