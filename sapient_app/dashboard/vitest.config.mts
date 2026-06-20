import { defineConfig } from "vitest/config";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [tsconfigPaths()],
  test: {
    environment: "node",
    include: ["src/**/__tests__/**/*.test.ts"],
    setupFiles: ["./src/lib/__tests__/_helpers/setup.ts"],
    hookTimeout: 30_000,
    testTimeout: 30_000,
    pool: "forks", // pglite has process-affinity behavior; forks keeps files isolated
  },
});
