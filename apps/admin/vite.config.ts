import { resolve } from 'node:path';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// Vite builds a strict-CSP-compatible bundle: no inline scripts/styles.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@lsc/api-client': resolve(__dirname, '../../packages/api-client/src/index.ts'),
      '@lsc/ui': resolve(__dirname, '../../packages/ui/src/index.ts'),
    },
  },
  build: {
    // Do not inline small assets as data: URIs (keeps the CSP strict).
    assetsInlineLimit: 0,
    sourcemap: true,
  },
});
