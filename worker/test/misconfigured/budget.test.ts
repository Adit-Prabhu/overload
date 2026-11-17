// Runs with a live provider selected but a malformed daily cap (see vitest.config.ts). The
// service must refuse to spend, count the refused attempts, and never reach the network.
import { exports } from "cloudflare:workers";
import { expect, it } from "vitest";

const BASE = "http://rival.test";
const SUMMARY = {
  items: [{ id: "e1.far_share", label: "far", value: 0.8 }],
  previous_tactic: "lateral",
};

async function ask(sessionId: string, requestId: string, encounter: number) {
  const response = await exports.default.fetch(`${BASE}/sessions/${sessionId}/tactic`, {
    method: "POST",
    body: JSON.stringify({ request_id: requestId, encounter, summary: SUMMARY }),
  });
  return (await response.json()) as Record<string, unknown>;
}

it("refuses live calls when the budget is malformed, and failed attempts still count", async () => {
  const created = await exports.default.fetch(`${BASE}/sessions`, { method: "POST" });
  const { session_id: id } = (await created.json()) as { session_id: string };
  const first = await ask(id, "request-0001", 2);
  expect(first).toMatchObject({ status: "budget", source: "live", tactic_id: null, attempts_used: 1 });
  expect(await ask(id, "request-0002", 3)).toMatchObject({ status: "budget", attempts_used: 2 });
  expect(await ask(id, "request-0003", 3)).toMatchObject({ status: "request_cap" });
});
