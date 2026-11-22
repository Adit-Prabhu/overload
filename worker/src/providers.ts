// Model providers. "vertex" is the live provider chosen in decision D6 (course credits,
// service account key as a Worker secret). "fixture" is a deterministic local rule whose
// results are always labeled source "fixture", so they are never mistaken for model evidence.

import { type Fetcher, type ServiceAccount, accessToken, parseServiceAccount } from "./google";
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
  warm?(signal: AbortSignal): Promise<boolean>;
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

  async warm(): Promise<boolean> {
    return false;
  }

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

export const MAX_INPUT_TOKENS = 1000;
export const MAX_OUTPUT_TOKENS = 512;

/** Rough token estimate (4 characters per token) used to refuse oversized prompts before
 *  anything is sent. The provider's own count is what gets logged. */
export function estimateTokens(prompt: PromptInput): number {
  return Math.ceil((prompt.system.length + prompt.user.length) / 4);
}

/** Gemini on Vertex AI through the REST API, authenticated with a service account key held
 *  as a Worker secret. Temperature 0, JSON constrained to the allowed tactics, no retries. */
export class VertexProvider implements Provider {
  readonly source = "live" as const;
  readonly requestedModel: string;

  constructor(
    private readonly account: ServiceAccount,
    private readonly project: string,
    private readonly location: string,
    model: string,
    private readonly tacticIds: string[],
    private readonly thinkingBudget: number | null,
    private readonly fetcher: Fetcher = (input, init) => fetch(input, init),
  ) {
    this.requestedModel = model;
  }

  endpoint(): string {
    const host =
      this.location === "global" ? "aiplatform.googleapis.com" : `${this.location}-aiplatform.googleapis.com`;
    return (
      `https://${host}/v1/projects/${this.project}/locations/${this.location}` +
      `/publishers/google/models/${this.requestedModel}:generateContent`
    );
  }

  body(prompt: PromptInput): Record<string, unknown> {
    const generationConfig: Record<string, unknown> = {
      temperature: 0,
      maxOutputTokens: MAX_OUTPUT_TOKENS,
      responseMimeType: "application/json",
      responseSchema: {
        type: "OBJECT",
        properties: {
          tactic_id: { type: "STRING", enum: this.tacticIds },
          evidence_ids: { type: "ARRAY", items: { type: "STRING" } },
        },
        required: ["tactic_id", "evidence_ids"],
      },
    };
    if (this.thinkingBudget !== null) generationConfig.thinkingConfig = { thinkingBudget: this.thinkingBudget };
    return {
      systemInstruction: { parts: [{ text: prompt.system }] },
      contents: [{ role: "user", parts: [{ text: prompt.user }] }],
      generationConfig,
    };
  }

  /** Pre-fetch and cache the service account OAuth token without calling generateContent. */
  async warm(signal: AbortSignal): Promise<boolean> {
    await accessToken(this.account, this.fetcher, Date.now, signal);
    return true;
  }

  async propose(prompt: PromptInput, _summary: Summary, signal: AbortSignal): Promise<ProviderResult> {
    if (estimateTokens(prompt) > MAX_INPUT_TOKENS) throw new Error("prompt over the input ceiling");
    const token = await accessToken(this.account, this.fetcher, Date.now, signal);
    const response = await this.fetcher(this.endpoint(), {
      method: "POST",
      headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
      body: JSON.stringify(this.body(prompt)),
      signal,
    });
    if (!response.ok) throw new Error(`Vertex returned HTTP ${response.status}`);
    const data = (await response.json()) as {
      candidates?: { content?: { parts?: { text?: string }[] }; finishReason?: string }[];
      usageMetadata?: { promptTokenCount?: number; candidatesTokenCount?: number; thoughtsTokenCount?: number };
      modelVersion?: string;
    };
    const candidate = data.candidates?.[0];
    const usage = data.usageMetadata ?? {};
    const truncated = candidate?.finishReason === "MAX_TOKENS";
    const text = (candidate?.content?.parts ?? []).map((part) => part.text ?? "").join("");
    return {
      raw: truncated ? "" : text, // a cut-off reply fails validation instead of being guessed at
      resolvedModel: data.modelVersion ?? this.requestedModel,
      inputTokens: usage.promptTokenCount ?? 0,
      outputTokens: (usage.candidatesTokenCount ?? 0) + (usage.thoughtsTokenCount ?? 0),
    };
  }
}

export function makeProvider(env: Env, tacticIds: string[] = [], fetcher?: Fetcher): Provider {
  const name = env.PROVIDER ?? "fixture";
  if (name === "fixture") return new FixtureProvider(Number(env.FIXTURE_DELAY_MS ?? 0));
  if (name === "vertex") {
    if (!env.GOOGLE_CLOUD_PROJECT || !env.MODEL || env.MODEL === "unset") {
      throw new ProviderNotConfigured("set GOOGLE_CLOUD_PROJECT and MODEL for Vertex");
    }
    let account: ServiceAccount;
    try {
      account = parseServiceAccount(env.GCP_SERVICE_ACCOUNT_JSON);
    } catch (error) {
      throw new ProviderNotConfigured(String(error));
    }
    const budget = env.THINKING_BUDGET === undefined || env.THINKING_BUDGET === "" ? null : Number(env.THINKING_BUDGET);
    return new VertexProvider(
      account,
      env.GOOGLE_CLOUD_PROJECT,
      env.GOOGLE_CLOUD_LOCATION ?? "global",
      env.MODEL,
      tacticIds,
      budget,
      fetcher,
    );
  }
  throw new ProviderNotConfigured(`unknown provider ${name}`);
}

/** Best-effort cold-start OAuth warm-up. Never calls a model, never spends budget, and
 *  returns false cleanly if the provider is fixture, unconfigured, or unreachable. */
export async function warmProvider(
  env: Env,
  signal?: AbortSignal,
  fetcher?: Fetcher,
): Promise<boolean> {
  try {
    const provider = makeProvider(env, [], fetcher);
    if (provider.source !== "live" || !provider.warm) return false;
    return await provider.warm(signal ?? AbortSignal.timeout(3000));
  } catch {
    return false;
  }
}
