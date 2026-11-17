// Builds the model input from the tactic catalogue and the filtered summary only.
// Nothing else is available here: the request schema has already rejected any other field.

import { CATALOGUE, NEUTRAL_TACTIC, type Summary } from "./schema";

export const SYSTEM_INSTRUCTIONS =
  "Select one allowed next-encounter tactic from the supplied catalogue using only observed " +
  "history. Return tactic_id and evidence_ids as JSON. Do not invent evidence or change game " +
  `rules. With insufficient evidence select ${NEUTRAL_TACTIC}.`;

export interface PromptInput {
  system: string;
  user: string;
}

export function buildPrompt(summary: Summary, history: Summary[]): PromptInput {
  const lines = [
    "Allowed tactics:",
    ...CATALOGUE.tactics.map((t) => `- ${t.id}: ${t.description}`),
    "",
    `Previous accepted tactic: ${summary.previous_tactic}`,
    "Observed in the last encounter (id: description = value):",
    ...summary.items.map((item) => `- ${item.id}: ${item.label} = ${item.value}`),
  ];
  if (history.length > 0) {
    lines.push("", "Earlier encounters in this session:");
    for (const earlier of history) {
      for (const item of earlier.items) lines.push(`- ${item.id}: ${item.label} = ${item.value}`);
    }
  }
  lines.push(
    "",
    'Reply with JSON only: {"tactic_id": "<one allowed id>", "evidence_ids": ["<ids you used>"]}',
  );
  return { system: SYSTEM_INSTRUCTIONS, user: lines.join("\n") };
}
