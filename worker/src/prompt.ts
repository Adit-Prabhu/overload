// Builds the model input from the tactic catalogue and the filtered summary only.
// Nothing else is available here: the request schema has already rejected any other field,
// and labels come from config/evidence.json rather than from the client.

import { CATALOGUE, EVIDENCE_LABELS, NEUTRAL_TACTIC, type EvidenceItem, type Summary } from "./schema";

/** The label comes from the server's own table, never from the client. */
function line(item: EvidenceItem): string {
  const kind = item.id.slice(item.id.indexOf(".") + 1);
  return `- ${item.id}: ${EVIDENCE_LABELS[kind]} = ${item.value}`;
}

export const SYSTEM_INSTRUCTIONS =
  "You choose the Regulator's tactic for the next encounter. The Regulator's goal is to counter " +
  "the habit the Surge relied on most in the observed history, so the player has to change " +
  "their approach. Select one allowed tactic from the supplied catalogue using only observed " +
  "history. Return tactic_id and evidence_ids as JSON, citing the evidence that shows the habit. " +
  "Do not invent evidence or change game rules. " +
  `With insufficient evidence or no dominant habit select ${NEUTRAL_TACTIC}.`;

export interface PromptInput {
  system: string;
  user: string;
}

export function buildPrompt(summary: Summary, history: Summary[]): PromptInput {
  const lines = [
    "Allowed tactics:",
    ...CATALOGUE.tactics.map((t) => `- ${t.id}: ${t.description} ${t.counters}`),
    "",
    `Previous accepted tactic: ${summary.previous_tactic}`,
    "Observed in the last encounter (id: description = value):",
    ...summary.items.map(line),
  ];
  if (history.length > 0) {
    lines.push("", "Earlier encounters in this session:");
    for (const earlier of history) {
      for (const item of earlier.items) lines.push(line(item));
    }
  }
  lines.push(
    "",
    'Reply with JSON only: {"tactic_id": "<one allowed id>", "evidence_ids": ["<ids you used>"]}',
  );
  return { system: SYSTEM_INSTRUCTIONS, user: lines.join("\n") };
}
