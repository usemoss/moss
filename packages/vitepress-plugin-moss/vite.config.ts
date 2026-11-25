import { defineConfig } from 'vite';
import dts from 'vite-plugin-dts';

export default defineConfig({
  build: {
    lib: {
      entry: 'index.ts',
      // ESM only, like VitePress itself. A CommonJS build can't load obug,
      // which is ESM-only and whose require() returns createDebug itself.
      formats: ['es'],
      fileName: () => 'index.js',
    },
    rollupOptions: {
      external: [
        'vite',
        'vitepress',
        'obug',
        '@moss-tools/md-indexer',
        'path',
        'fs',
        'url',
        'node:path',
        'node:fs',
        'node:url',
      ],
    },
  },
  plugins: [
    dts({ insertTypesEntry: true, bundleTypes: true }),
  ],
});
