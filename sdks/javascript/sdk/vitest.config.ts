import { defineConfig } from 'vitest/config';
import dotenv from 'dotenv';

// Load .env file before tests run
dotenv.config();

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    exclude: [
      "test/create_index_versions.test.ts",
      "test/search.test.ts",
    ],
    // Force Vitest to use child_process (forks) instead of worker_threads
    // This resolves "Module did not self-register" errors with native C++ addons
    pool: 'forks',
    reporters: ['verbose'],
    testTimeout: 200000,
    fileParallelism: false,
    hookTimeout: 200000,
  },
});
