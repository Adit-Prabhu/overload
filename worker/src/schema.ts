// Request and response shapes for the rival service, and the tactic catalogue.
// Schemas are strict: unknown fields are rejected, so the game cannot send hidden state
// (positions, health, inventory, RNG) even by mistake. That is the knowledge boundary.

import { z } from "zod";
import evidence from "../../config/evidence.json";
import catalogue from "../../config/tactics.json";

export const TACTIC_IDS = catalogue.tactics.map((t) => t.id) as [string, ...string[]];
export const NEUTRAL_TACTIC = catalogue.neutral;
export const CATALOGUE = catalogue;
/** Observation kinds and the labels the server writes into prompts. */
export const EVIDENCE_LABELS: Record<string, string> = evidence.kinds;
const KIND_PATTERN = Object.keys(evidence.kinds).join("|");

export const MAX_ATTEMPTS_PER_SESSION = 2;
export const MAX_SUMMARY_ITEMS = 12;
export const HISTORY_LIMIT = 2;
export const SESSION_TTL_SECONDS = 30 * 60;
export const PROVIDER_DEADLINE_MS = 4500; // the client's hard deadline is 5 s

export const EvidenceItem = z
  .object({
    id: z.string().regex(new RegExp(`^e[0-9]\\.(${KIND_PATTERN})$`)),
    label: z.string().min(1).max(80),
    value: z.number().finite(),
  })
  .strict();

export const Summary = z
  .object({
    items: z.array(EvidenceItem).min(1).max(MAX_SUMMARY_ITEMS),
    previous_tactic: z.enum(TACTIC_IDS),
  })
  .strict();

export const TacticRequest = z
  .object({
    request_id: z.string().regex(/^[A-Za-z0-9-]{8,64}$/),
    encounter: z.union([z.literal(2), z.literal(3)]),
    summary: Summary,
  })
  .strict();

export const Proposal = z
  .object({
    tactic_id: z.enum(TACTIC_IDS),
    evidence_ids: z.array(z.string()).max(MAX_SUMMARY_ITEMS),
  })
  .strict();

export type EvidenceItem = z.infer<typeof EvidenceItem>;
export type Summary = z.infer<typeof Summary>;
export type TacticRequest = z.infer<typeof TacticRequest>;
export type Proposal = z.infer<typeof Proposal>;

export type Status =
  | "ok"
  | "invalid_output"
  | "timeout"
  | "provider_error"
  | "provider_not_configured"
  | "request_cap"
  | "duplicate_request"
  | "encounter_order"
  | "budget"
  | "internal_error"; // the service itself failed (not the model): labelled, never a raw 500

/** "none" means no provider answered (for example, none is configured). */
export type Source = "fixture" | "live" | "none";

export interface TacticResponse {
  session_id: string;
  request_id: string;
  encounter: number;
  status: Status;
  tactic_id: string | null;
  evidence_ids: string[];
  source: Source;
  requested_model: string;
  resolved_model: string | null;
  latency_ms: number;
  usage: { input_tokens: number; output_tokens: number };
  cost_usd_estimate: number;
  attempts_used: number;
}

/** Check a model's raw JSON against the schema and the evidence actually supplied. */
export function validateProposal(raw: string, summary: Summary): Proposal | null {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  const result = Proposal.safeParse(parsed);
  if (!result.success) return null;
  const supplied = new Set(summary.items.map((item) => item.id));
  if (!result.data.evidence_ids.every((id) => supplied.has(id))) return null;
  return result.data;
}
