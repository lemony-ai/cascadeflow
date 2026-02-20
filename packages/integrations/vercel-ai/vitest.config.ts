import { defineConfig } from 'vitest/config';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const rootDir = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      '@cascadeflow/core': resolve(rootDir, '../../core/src/index.ts'),
      '@cascadeflow/ml': resolve(rootDir, '../../ml/src/index.ts'),
    },
  },
});
