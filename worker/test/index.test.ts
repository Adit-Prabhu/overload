import { exports } from "cloudflare:workers";
import { describe, expect, it } from "vitest";

describe("rival service scaffold", () => {
  it("reports health", async () => {
    const response = await exports.default.fetch("http://rival.test/health");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      ok: true,
      service: "overload-rival",
      stage: "scaffold",
    });
  });

  it("returns 404 for unknown routes", async () => {
    const response = await exports.default.fetch("http://rival.test/sessions");
    expect(response.status).toBe(404);
  });
});
