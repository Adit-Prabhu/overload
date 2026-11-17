import { env, exports } from "cloudflare:workers";
import { getAgentByName } from "agents";
import { describe, expect, it } from "vitest";
import { buildPrompt } from "../src/prompt";
import { FixtureProvider } from "../src/providers";
import { type Summary, validateProposal } from "../src/schema";

const BASE = "http://rival.test";

function summary(far: number, near: number, previous = "lateral"): Summary {
  return {
    items: [
      { id: "e1.far_share", label: "share of visible time the player spent far away", value: far },
      { id: "e1.near_share", label: "share of visible time the player spent close", value: near },
      { id: "e1.spark_uses", label: "Spark uses", value: 3 },
    ],
    previous_tactic: previous,
  };
}

async function startSession(): Promise<string> {
  const response = await exports.default.fetch(`${BASE}/sessions`, { method: "POST" });
  expect(response.status).toBe(201);
  const body = (await response.json()) as { session_id: string };
  expect(body.session_id).toMatch(/^[0-9a-f-]{36}$/);
  return body.session_id;
}

async function ask(sessionId: string, body: unknown) {
  const response = await exports.default.fetch(`${BASE}/sessions/${sessionId}/tactic`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  return { status: response.status, body: (await response.json()) as Record<string, unknown> };
}

let counter = 0;
function request(encounter: number, s: Summary) {
  counter += 1;
  return { request_id: `req-${counter.toString().padStart(8, "0")}`, encounter, summary: s };
}

describe("routes", () => {
  it("reports health and the configured provider", async () => {
    const response = await exports.default.fetch(`${BASE}/health`);
    expect(await response.json()).toEqual({ ok: true, service: "overload-rival", provider: "fixture" });
  });

  it("rejects unknown sessions", async () => {
    const result = await ask("00000000-0000-0000-0000-000000000000", request(2, summary(0.8, 0.1)));
    expect(result.status).toBe(404);
  });

  it("rejects fields outside the schema, so hidden state cannot be sent", async () => {
    const id = await startSession();
    const leaky = { ...request(2, summary(0.8, 0.1)), world: { player_hp: 3 } };
    expect((await ask(id, leaky)).status).toBe(400);
    const leakyItem = request(2, summary(0.8, 0.1));
    (leakyItem.summary.items[0] as Record<string, unknown>).hidden_inventory = ["burst"];
    expect((await ask(id, leakyItem)).status).toBe(400);
  });
});

describe("tactic proposals (fixture provider)", () => {
  it("counters a long-range habit with pressure and cites the evidence", async () => {
    const id = await startSession();
    const result = await ask(id, request(2, summary(0.8, 0.1)));
    expect(result.status).toBe(200);
    expect(result.body).toMatchObject({
      status: "ok",
      tactic_id: "pressure",
      evidence_ids: ["e1.far_share"],
      source: "fixture",
      attempts_used: 1,
    });
  });

  it("counters close-range play with spacing and stays neutral otherwise", async () => {
    const a = await startSession();
    expect((await ask(a, request(2, summary(0.1, 0.7)))).body.tactic_id).toBe("spacing");
    const b = await startSession();
    expect((await ask(b, request(2, summary(0.3, 0.3)))).body.tactic_id).toBe("lateral");
  });

  it("allows two attempts per session, counting every attempt", async () => {
    const id = await startSession();
    expect((await ask(id, request(2, summary(0.8, 0.1)))).body.status).toBe("ok");
    expect((await ask(id, request(3, summary(0.8, 0.1)))).body.status).toBe("ok");
    const third = await ask(id, request(3, summary(0.8, 0.1)));
    expect(third.body.status).toBe("request_cap");
    expect(third.body.tactic_id).toBeNull();
  });

  it("refuses a repeated request id and out-of-order encounters", async () => {
    const id = await startSession();
    const first = request(2, summary(0.8, 0.1));
    expect((await ask(id, first)).body.status).toBe("ok");
    expect((await ask(id, first)).body.status).toBe("duplicate_request");
    expect((await ask(id, request(2, summary(0.8, 0.1)))).body.status).toBe("encounter_order");
  });

  it("keeps each session's history separate", async () => {
    const a = await startSession();
    const b = await startSession();
    await ask(a, request(2, summary(0.9, 0.0)));
    await ask(b, request(2, summary(0.0, 0.9)));
    const historyA = await (await getAgentByName(env.RIVAL_SESSION, a)).history();
    const historyB = await (await getAgentByName(env.RIVAL_SESSION, b)).history();
    expect(historyA).toHaveLength(1);
    expect(historyB).toHaveLength(1);
    expect(historyA[0].items[0].value).toBe(0.9);
    expect(historyB[0].items[0].value).toBe(0.0);
  });

  it("forgets everything when a session expires", async () => {
    const id = await startSession();
    await ask(id, request(2, summary(0.8, 0.1)));
    const session = await getAgentByName(env.RIVAL_SESSION, id);
    await session.expire();
    expect(await session.isStarted()).toBe(false);
    expect(await session.history()).toEqual([]);
    expect((await ask(id, request(3, summary(0.8, 0.1)))).status).toBe(404);
  });
});

describe("validation", () => {
  const s = summary(0.8, 0.1);

  it("accepts a proposal that cites supplied evidence", () => {
    expect(validateProposal('{"tactic_id":"pressure","evidence_ids":["e1.far_share"]}', s)).toEqual({
      tactic_id: "pressure",
      evidence_ids: ["e1.far_share"],
    });
  });

  it.each([
    ["not JSON", "pressure please"],
    ["unknown tactic", '{"tactic_id":"berserk","evidence_ids":[]}'],
    ["invented evidence", '{"tactic_id":"pressure","evidence_ids":["e1.player_hp"]}'],
    ["extra field", '{"tactic_id":"pressure","evidence_ids":[],"damage":99}'],
  ])("rejects %s", (_name, raw) => {
    expect(validateProposal(raw, s)).toBeNull();
  });
});

describe("knowledge boundary and limits", () => {
  it("builds the prompt only from the catalogue and the supplied summary", () => {
    const prompt = buildPrompt(summary(0.8, 0.1), []);
    expect(prompt.user).toContain("e1.far_share");
    expect(prompt.user).toContain("pressure");
    expect(prompt.system).toContain("insufficient evidence select lateral");
    expect(prompt.user).not.toMatch(/hp|health|inventory|seed|position/i);
  });

  it("gives up at the deadline", async () => {
    const slow = new FixtureProvider(200);
    const prompt = buildPrompt(summary(0.8, 0.1), []);
    await expect(slow.propose(prompt, summary(0.8, 0.1), AbortSignal.timeout(20))).rejects.toThrow();
  });

  it("refuses spending beyond the daily cap", async () => {
    const ledger = env.BUDGET.get(env.BUDGET.idFromName("test-ledger"));
    expect(await ledger.reserve(0.6, 1.0)).toBe(true);
    expect(await ledger.reserve(0.6, 1.0)).toBe(false);
  });
});
