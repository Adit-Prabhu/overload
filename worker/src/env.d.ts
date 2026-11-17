// Bindings and configuration available to the Worker. The one secret,
// GCP_SERVICE_ACCOUNT_JSON, is set with `wrangler secret put` and never committed.
declare namespace Cloudflare {
  interface Env {
    RIVAL_SESSION: DurableObjectNamespace<import("./session").RivalSession>;
    BUDGET: DurableObjectNamespace<import("./budget").BudgetLedger>;
    PROVIDER?: string;
    MODEL?: string;
    FIXTURE_DELAY_MS?: string;
    DAILY_BUDGET_USD?: string;
    INPUT_USD_PER_M?: string;
    OUTPUT_USD_PER_M?: string;
    GOOGLE_CLOUD_PROJECT?: string;
    GOOGLE_CLOUD_LOCATION?: string;
    THINKING_BUDGET?: string;
    GCP_SERVICE_ACCOUNT_JSON?: string;
  }

  interface GlobalProps {
    mainModule: typeof import("./index");
    durableNamespaces: "RivalSession" | "BudgetLedger";
  }
}

interface Env extends Cloudflare.Env {}
