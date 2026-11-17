import { cloudflareTest } from "@cloudflare/vitest-plugin";
import { defineConfig } from "vitest/config";

const FAKE_ACCOUNT = JSON.stringify({
  client_email: "rival@test.iam.gserviceaccount.com",
  private_key: "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----\n",
});

export default defineConfig({
  test: {
    projects: [
      {
        plugins: [cloudflareTest({ wrangler: { configPath: "./wrangler.jsonc" } })],
        test: { name: "service", include: ["test/*.test.ts"] },
      },
      {
        // A live provider selected with a malformed cap: proves the budget fails closed.
        plugins: [
          cloudflareTest({
            wrangler: { configPath: "./wrangler.jsonc" },
            miniflare: {
              bindings: {
                PROVIDER: "vertex",
                MODEL: "gemini-test",
                GOOGLE_CLOUD_PROJECT: "test-project",
                GCP_SERVICE_ACCOUNT_JSON: FAKE_ACCOUNT,
                DAILY_BUDGET_USD: "not-a-number",
              },
            },
          }),
        ],
        test: { name: "misconfigured", include: ["test/misconfigured/*.test.ts"] },
      },
    ],
  },
});
