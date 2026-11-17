// One rival session per player session, as a Cloudflare Agent (a Durable Object with state).
// Each session sees only its own history. Sessions expire after 30 minutes of inactivity.

import { Agent } from "agents";
import { liveBudget } from "./budget";
import { buildPrompt } from "./prompt";
import { ProviderNotConfigured, makeProvider } from "./providers";
import {
  HISTORY_LIMIT,
  MAX_ATTEMPTS_PER_SESSION,
  PROVIDER_DEADLINE_MS,
  SESSION_TTL_SECONDS,
  TACTIC_IDS,
  type Status,
  type Summary,
  type TacticRequest,
  type TacticResponse,
  validateProposal,
} from "./schema";

export interface SessionState {
  started: boolean;
  attempts: number;
  lastEncounter: number;
  requestIds: string[];
  history: Summary[];
  expiryId: string | null;
}

export class RivalSession extends Agent<Env, SessionState> {
  initialState: SessionState = {
    started: false,
    attempts: 0,
    lastEncounter: 1,
    requestIds: [],
    history: [],
    expiryId: null,
  };

  async begin(): Promise<void> {
    this.setState({ ...this.state, started: true });
    await this.refreshExpiry();
  }

  isStarted(): boolean {
    return this.state.started;
  }

  history(): Summary[] {
    return this.state.history;
  }

  /** Scheduled after 30 minutes without a request. Wipes history, counters and request IDs,
   *  so nothing from this session can reach a later one. */
  async expire(): Promise<void> {
    if (this.state.expiryId) await this.cancelSchedule(this.state.expiryId);
    this.setState({ ...this.initialState });
  }

  private async refreshExpiry(): Promise<void> {
    if (this.state.expiryId) await this.cancelSchedule(this.state.expiryId);
    const schedule = await this.schedule(SESSION_TTL_SECONDS, "expire");
    this.setState({ ...this.state, expiryId: schedule.id });
  }

  async propose(request: TacticRequest, sessionId: string): Promise<TacticResponse> {
    const started = Date.now();
    const state = this.state;
    let provider: ReturnType<typeof makeProvider> | null = null;
    let configError = false;
    try {
      provider = makeProvider(this.env, TACTIC_IDS);
    } catch (error) {
      if (!(error instanceof ProviderNotConfigured)) throw error;
      configError = true;
    }
    const base: TacticResponse = {
      session_id: sessionId,
      request_id: request.request_id,
      encounter: request.encounter,
      status: "ok",
      tactic_id: null,
      evidence_ids: [],
      source: provider?.source ?? "none",
      requested_model: provider?.requestedModel ?? String(this.env.MODEL ?? "unset"),
      resolved_model: null,
      latency_ms: 0,
      usage: { input_tokens: 0, output_tokens: 0 },
      cost_usd_estimate: 0,
      attempts_used: state.attempts,
    };
    const refuse = (status: Status): TacticResponse => ({
      ...base,
      status,
      latency_ms: Date.now() - started,
    });

    if (state.requestIds.includes(request.request_id)) return refuse("duplicate_request");
    if (state.attempts >= MAX_ATTEMPTS_PER_SESSION) return refuse("request_cap");
    if (request.encounter <= state.lastEncounter) return refuse("encounter_order");

    // From here on the attempt counts, whatever happens.
    const attempts = state.attempts + 1;
    this.setState({
      ...state,
      attempts,
      lastEncounter: request.encounter,
      requestIds: [...state.requestIds, request.request_id],
      history: [...state.history, request.summary].slice(-HISTORY_LIMIT),
    });
    await this.refreshExpiry();
    const counted = { ...base, attempts_used: attempts };

    if (configError || !provider) {
      return { ...counted, status: "provider_not_configured", latency_ms: Date.now() - started };
    }
    let cost = 0;
    if (provider.source === "live") {
      const budget = liveBudget(this.env);
      const ledger = this.env.BUDGET.get(this.env.BUDGET.idFromName("global"));
      if (!budget || !(await ledger.reserve(budget.costUsd, budget.capUsd))) {
        return { ...counted, status: "budget", latency_ms: Date.now() - started };
      }
      cost = budget.costUsd;
    }

    const prompt = buildPrompt(request.summary, state.history);
    try {
      const result = await provider.propose(
        prompt,
        request.summary,
        AbortSignal.timeout(PROVIDER_DEADLINE_MS),
      );
      const proposal = validateProposal(result.raw, request.summary);
      return {
        ...counted,
        status: proposal ? "ok" : "invalid_output",
        tactic_id: proposal?.tactic_id ?? null,
        evidence_ids: proposal?.evidence_ids ?? [],
        resolved_model: result.resolvedModel,
        latency_ms: Date.now() - started,
        usage: { input_tokens: result.inputTokens, output_tokens: result.outputTokens },
        cost_usd_estimate: cost,
      };
    } catch (error) {
      const timedOut = error instanceof DOMException && error.name === "TimeoutError";
      return {
        ...counted,
        status: timedOut ? "timeout" : "provider_error",
        latency_ms: Date.now() - started,
        cost_usd_estimate: cost,
      };
    }
  }
}
