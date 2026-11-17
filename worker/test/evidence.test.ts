// Power-use evidence (task 8c): the service accepts the new kinds from config/evidence.json
// and writes its own labels into the prompt.
import { describe, expect, it } from "vitest";
import { buildPrompt } from "../src/prompt";
import { EVIDENCE_LABELS, Summary, validateProposal } from "../src/schema";

const summary = {
  items: [
    { id: "e2.far_share", label: "far", value: 0.2 },
    { id: "e2.blink_uses", label: "client text is ignored", value: 9 },
    { id: "e2.spark_uses", label: "client text is ignored", value: 4 },
    { id: "e2.arc_trail_uses", label: "client text is ignored", value: 0 },
  ],
  previous_tactic: "lateral",
};

describe("power-use evidence", () => {
  it("lists the five power kinds with server-side labels", () => {
    expect(EVIDENCE_LABELS.spark_uses).toBe("Spark power shots used");
    expect(EVIDENCE_LABELS.blink_uses).toBe("Blink teleports used");
    expect(EVIDENCE_LABELS.arc_trail_uses).toBe("Arc Trail teleports used");
    expect(EVIDENCE_LABELS.burst_uses).toBe("Burst shockwaves used");
    expect(EVIDENCE_LABELS.shock_cone_uses).toBe("Shock Cone blasts used");
  });

  it("passes the strict request schema", () => {
    expect(Summary.safeParse(summary).success).toBe(true);
    const burst = { ...summary, items: [{ id: "e2.shock_cone_uses", label: "x", value: 1 }] };
    expect(Summary.safeParse(burst).success).toBe(true);
    const unknown = { ...summary, items: [{ id: "e2.charge_left", label: "x", value: 1 }] };
    expect(Summary.safeParse(unknown).success).toBe(false);
  });

  it("puts the server's label, never the client's, in the prompt", () => {
    const prompt = buildPrompt(summary as never, []);
    expect(prompt.user).toContain("- e2.blink_uses: Blink teleports used = 9");
    expect(prompt.user).not.toContain("client text is ignored");
  });

  it("accepts a proposal that cites power evidence that was supplied", () => {
    expect(validateProposal('{"tactic_id":"pressure","evidence_ids":["e2.blink_uses"]}', summary as never)).toEqual({
      tactic_id: "pressure",
      evidence_ids: ["e2.blink_uses"],
    });
  });
});
