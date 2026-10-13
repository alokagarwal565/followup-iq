import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  // One backend and one database schema are shared, so tests run in order, not in parallel.
  workers: 1,
  fullyParallel: false,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: { baseURL: "http://localhost:3001", trace: "retain-on-failure" },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    { name: "mobile", use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } } },
  ],
  webServer: [
    {
      command: "node scripts/e2e-backend.mjs",
      url: "http://localhost:8001/health",
      timeout: 240_000,
      reuseExistingServer: false,
    },
    {
      command: "node scripts/e2e-frontend.mjs",
      url: "http://localhost:3001",
      timeout: 300_000,
      reuseExistingServer: false,
    },
  ],
});
