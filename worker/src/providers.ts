// Model providers. Only the deterministic "fixture" provider exists until Adit decides the
// live provider and credential path (decision D6). Fixture results are always labeled
// source "fixture" so they can never be mistaken for live model evidence.

import type { PromptInput } from "./prompt";
import type { Summary } from "./schema";

export interface ProviderResult {
  raw: string;
  resolvedModel: string | null;
  inputTokens: number;
  outputTokens: number;
}

export interface Provider {
  readonly source: "fixture" | "live";
  readonly requestedModel: string;
  propose(prompt: PromptInput, summary: Summary, signal: AbortSignal): Promise<ProviderResult>;
}

export class ProviderNotConfigured extends Error {}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) return reject(signal.reason);
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(signal.reason);
    });
  });
}

/** Deterministic stand-in: counters a dominant range habit, otherwise stays neutral.
 *  `delayMs` lets tests force a timeout. */
export class FixtureProvider implements Provider {
  readonly source = "fixture" as const;
  readonly requestedModel = "fixture-rule-v1";

  constructor(private readonly delayMs = 0) {}

  async propose(prompt: PromptInput, summary: Summary, signal: AbortSignal): Promise<ProviderResult> {
    if (this.delayMs > 0) await sleep(this.delayMs, signal);
    const find = (suffix: string) => summary.items.find((item) => item.id.endsWith(suffix));
    const far = find(".far_share");
    const near = find(".near_share");
    let choice = { tactic_id: "lateral", evidence_ids: [] as string[] };
    if (far && far.value >= 0.5) choice = { tactic_id: "pressure", evidence_ids: [far.id] };
    else if (near && near.value >= 0.5) choice = { tactic_id: "spacing", evidence_ids: [near.id] };
    const raw = JSON.stringify(choice);
    return {
      raw,
      resolvedModel: this.requestedModel,
      inputTokens: Math.ceil((prompt.system.length + prompt.user.length) / 4),
      outputTokens: Math.ceil(raw.length / 4),
    };
  }
}

export function makeProvider(env: Env): Provider {
  const name = env.PROVIDER ?? "fixture";
  if (name === "fixture") return new FixtureProvider(Number(env.FIXTURE_DELAY_MS ?? 0));
  throw new ProviderNotConfigured(`provider ${name} is not implemented yet (decision D6)`);
}
