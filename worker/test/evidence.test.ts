// Power-use evidence (evidence version 4): the service accepts the family kinds from
// config/evidence.json and writes its own labels into the prompt.
import { describe, expect, it } from "vitest";
import histories from "../../eval/histories.json";
import { buildPrompt } from "../src/prompt";
import { estimateTokens, MAX_INPUT_TOKENS } from "../src/providers";
import { EVIDENCE_LABELS, Summary, validateProposal } from "../src/schema";

const summary = {
  items: [
    { id: "e2.far_share", label: "far", value: 0.2 },
    { id: "e2.teleport_uses", label: "client text is ignored", value: 9 },
    { id: "e2.shot_power_uses", label: "client text is ignored", value: 4 },
    { id: "e2.shield_uses", label: "client text is ignored", value: 0 },
  ],
  previous_tactic: "lateral",
};

describe("power-use evidence", () => {
  it("lists the five power family kinds with server-side labels", () => {
    expect(EVIDENCE_LABELS.shot_power_uses).toBe("Spark-type shots used");
    expect(EVIDENCE_LABELS.teleport_uses).toBe("Teleports used");
    expect(EVIDENCE_LABELS.pulse_uses).toBe("Pulse blasts used");
    expect(EVIDENCE_LABELS.shield_uses).toBe("Shields raised");
    expect(EVIDENCE_LABELS.pull_uses).toBe("Pull fields used");
    expect(EVIDENCE_LABELS.spark_uses).toBeUndefined(); // version 3 kinds are gone
  });

  it("passes the strict request schema", () => {
    expect(Summary.safeParse(summary).success).toBe(true);
    const burst = { ...summary, items: [{ id: "e2.pulse_uses", label: "x", value: 1 }] };
    expect(Summary.safeParse(burst).success).toBe(true);
    const unknown = { ...summary, items: [{ id: "e2.charge_left", label: "x", value: 1 }] };
    expect(Summary.safeParse(unknown).success).toBe(false);
    const old = { ...summary, items: [{ id: "e2.blink_uses", label: "x", value: 1 }] };
    expect(Summary.safeParse(old).success).toBe(false); // a version 3 client is rejected
  });

  it("puts the server's label, never the client's, in the prompt", () => {
    const prompt = buildPrompt(summary as never, []);
    expect(prompt.user).toContain("- e2.teleport_uses: Teleports used = 9");
    expect(prompt.user).not.toContain("client text is ignored");
    expect(prompt.user).toContain("Spark-type shots");
    expect(prompt.user).toContain("shields and pull fields");
    expect(prompt.user).toContain("dives in with teleports");
    expect(prompt.user).toContain("pulse blasts");
    expect(prompt.user).toContain("power-family");
  });

  it("validates every authored v4 history case and stays under MAX_INPUT_TOKENS at encounter 3", () => {
    expect(histories.version).toBe(2);
    for (const c of histories.cases) {
      const items = Object.entries(c.values).map(([kind, value]) => ({
        id: `e1.${kind}`,
        label: EVIDENCE_LABELS[kind] ?? kind,
        value,
      }));
      const enc2 = { items, previous_tactic: "lateral" };
      expect(Summary.safeParse(enc2).success).toBe(true);
      const enc3 = {
        items: items.map((item) => ({ ...item, id: item.id.replace("e1.", "e2.") })),
        previous_tactic: c.intended,
      };
      expect(Summary.safeParse(enc3).success).toBe(true);
      const prompt = buildPrompt(enc3 as never, [enc2 as never]);
      expect(estimateTokens(prompt)).toBeLessThanOrEqual(MAX_INPUT_TOKENS);
    }
  });

  it("accepts a proposal that cites power evidence that was supplied", () => {
    expect(validateProposal('{"tactic_id":"pressure","evidence_ids":["e2.teleport_uses"]}', summary as never)).toEqual({
      tactic_id: "pressure",
      evidence_ids: ["e2.teleport_uses"],
    });
  });
});
