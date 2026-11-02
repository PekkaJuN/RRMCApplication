import { defineConfig, devices } from "@playwright/test";

// Runs in the e2e container: Playwright starts Vite, which forwards /api to backend-e2e.
export default defineConfig({
  testDir: "./e2e",
  forbidOnly: true,
  reporter: "list",
  use: { baseURL: "http://127.0.0.1:5173" },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] }, testIgnore: /style\.spec\.ts/ },
    // After the other specs: the style tests import a receipt of their own, and the import
    // journeys empty the import folder and start imports (styling spec P6).
    {
      name: "style",
      use: { ...devices["Desktop Chrome"] },
      testMatch: /style\.spec\.ts/,
      dependencies: ["chromium"],
    },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: false,
  },
});
