import { defineConfig } from "vitest/config";

// Unit tests cover the pure logic modules only (no DOM), so the plain node environment is enough.
export default defineConfig({
  test: { environment: "node", include: ["src/**/*.test.ts"] },
});
