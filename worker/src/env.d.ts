// Bindings and configuration available to the Worker. Secrets (a provider API key, once
// decision D6 picks a provider) are set with `wrangler secret put` and never committed.
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
  }

  interface GlobalProps {
    mainModule: typeof import("./index");
    durableNamespaces: "RivalSession" | "BudgetLedger";
  }
}

interface Env extends Cloudflare.Env {}
