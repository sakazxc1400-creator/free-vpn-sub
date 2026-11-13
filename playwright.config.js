import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./site/tests",
  timeout: 30000,
  use: { baseURL: "http://127.0.0.1:4173", browserName: "chromium", trace: "retain-on-failure" },
  webServer: { command: "npm run preview -- --port 4173 --strictPort", url: "http://127.0.0.1:4173", reuseExistingServer: !process.env.CI },
  reporter: "list",
});
