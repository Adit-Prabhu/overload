// The Vertex provider against a fake Google endpoint. Nothing here touches the network.

import { beforeEach, describe, expect, it } from "vitest";
import { type ServiceAccount, forgetToken } from "../src/google";
import { buildPrompt } from "../src/prompt";
import { ProviderNotConfigured, VertexProvider, makeProvider, warmProvider } from "../src/providers";
import type { Summary } from "../src/schema";

const SUMMARY: Summary = {
  items: [{ id: "e1.far_share", label: "share of the fight the Surge spent far away", value: 0.8 }],
  previous_tactic: "lateral",
};


function decode(part: string): Record<string, unknown> {
  const padded = part.replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(padded + "=".repeat((4 - (padded.length % 4)) % 4)));
}

async function testAccount(): Promise<{ account: ServiceAccount; publicKey: CryptoKey }> {
  const pair = (await crypto.subtle.generateKey(
    { name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" },
    true,
    ["sign", "verify"],
  )) as CryptoKeyPair;
  const der = (await crypto.subtle.exportKey("pkcs8", pair.privateKey)) as ArrayBuffer;
  let binary = "";
  for (const byte of new Uint8Array(der)) binary += String.fromCharCode(byte);
  const pem = `-----BEGIN PRIVATE KEY-----\n${btoa(binary)}\n-----END PRIVATE KEY-----\n`;
  return { account: { client_email: "rival@test.iam.gserviceaccount.com", private_key: pem }, publicKey: pair.publicKey };
}

interface Call {
  url: string;
  init?: RequestInit;
}

function fakeGoogle(reply: Record<string, unknown>) {
  const calls: Call[] = [];
  const fetcher = async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    if (url.includes("oauth2.googleapis.com")) {
      return Response.json({ access_token: "token-123", expires_in: 3600 });
    }
    return Response.json(reply);
  };
  return { calls, fetcher };
}

const OK_REPLY = {
  candidates: [{ content: { parts: [{ text: '{"tactic_id":"pressure","evidence_ids":["e1.far_share"]}' }] }, finishReason: "STOP" }],
  usageMetadata: { promptTokenCount: 210, candidatesTokenCount: 18, thoughtsTokenCount: 0 },
  modelVersion: "gemini-3.5-flash-lite-001",
};

beforeEach(() => forgetToken());

describe("Vertex provider", () => {
  it("signs a valid service account assertion and calls generateContent", async () => {
    const { account, publicKey } = await testAccount();
    const google = fakeGoogle(OK_REPLY);
    const provider = new VertexProvider(account, "course-project", "global", "gemini-3.5-flash-lite",
      ["pressure", "spacing", "lateral"], 0, google.fetcher);
    const result = await provider.propose(buildPrompt(SUMMARY, []), SUMMARY, AbortSignal.timeout(1000));

    const tokenCall = google.calls[0];
    const assertion = new URLSearchParams(String(tokenCall.init?.body)).get("assertion") ?? "";
    const [header, claims, signature] = assertion.split(".");
    expect(decode(claims)).toMatchObject({
      iss: account.client_email,
      aud: "https://oauth2.googleapis.com/token",
      scope: "https://www.googleapis.com/auth/cloud-platform",
    });
    const sig = Uint8Array.from(atob(signature.replace(/-/g, "+").replace(/_/g, "/") + "==".slice(0, (4 - (signature.length % 4)) % 4)), (c) => c.charCodeAt(0));
    const valid = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", publicKey, sig, new TextEncoder().encode(`${header}.${claims}`));
    expect(valid).toBe(true);

    const call = google.calls[1];
    expect(call.url).toBe(
      "https://aiplatform.googleapis.com/v1/projects/course-project/locations/global/publishers/google/models/gemini-3.5-flash-lite:generateContent",
    );
    expect((call.init?.headers as Record<string, string>).authorization).toBe("Bearer token-123");
    const body = JSON.parse(String(call.init?.body));
    expect(body.generationConfig).toMatchObject({
      temperature: 0,
      maxOutputTokens: 512,
      responseMimeType: "application/json",
      thinkingConfig: { thinkingBudget: 0 },
    });
    expect(body.generationConfig.responseSchema.properties.tactic_id.enum).toEqual(["pressure", "spacing", "lateral"]);
    expect(result).toEqual({
      raw: '{"tactic_id":"pressure","evidence_ids":["e1.far_share"]}',
      resolvedModel: "gemini-3.5-flash-lite-001",
      inputTokens: 210,
      outputTokens: 18,
    });
  });

  it("reuses the access token and counts thinking as output", async () => {
    const { account } = await testAccount();
    const reply = { ...OK_REPLY, usageMetadata: { promptTokenCount: 200, candidatesTokenCount: 10, thoughtsTokenCount: 40 } };
    const google = fakeGoogle(reply);
    const provider = new VertexProvider(account, "p", "us-central1", "m", ["lateral"], null, google.fetcher);
    await provider.propose(buildPrompt(SUMMARY, []), SUMMARY, AbortSignal.timeout(1000));
    const second = await provider.propose(buildPrompt(SUMMARY, []), SUMMARY, AbortSignal.timeout(1000));
    expect(google.calls.filter((c) => c.url.includes("oauth2")).length).toBe(1);
    expect(google.calls[1].url).toContain("https://us-central1-aiplatform.googleapis.com/");
    expect(JSON.parse(String(google.calls[1].init?.body)).generationConfig.thinkingConfig).toBeUndefined();
    expect(second.outputTokens).toBe(50);
  });

  it("treats a truncated reply as invalid rather than guessing", async () => {
    const { account } = await testAccount();
    const google = fakeGoogle({ ...OK_REPLY, candidates: [{ content: { parts: [{ text: '{"tactic_id":"pre' }] }, finishReason: "MAX_TOKENS" }] });
    const provider = new VertexProvider(account, "p", "global", "m", ["lateral"], 0, google.fetcher);
    expect((await provider.propose(buildPrompt(SUMMARY, []), SUMMARY, AbortSignal.timeout(1000))).raw).toBe("");
  });

  it("refuses an oversized prompt before sending anything", async () => {
    const { account } = await testAccount();
    const google = fakeGoogle(OK_REPLY);
    const provider = new VertexProvider(account, "p", "global", "m", ["lateral"], 0, google.fetcher);
    const huge = { system: "x".repeat(5000), user: "y" };
    await expect(provider.propose(huge, SUMMARY, AbortSignal.timeout(1000))).rejects.toThrow("input ceiling");
    expect(google.calls).toHaveLength(0);
  });

  it("fails safe when Vertex is selected but not configured", () => {
    expect(() => makeProvider({ PROVIDER: "vertex" } as Env)).toThrow(ProviderNotConfigured);
    expect(() =>
      makeProvider({ PROVIDER: "vertex", GOOGLE_CLOUD_PROJECT: "p", MODEL: "m", GCP_SERVICE_ACCOUNT_JSON: "{}" } as Env),
    ).toThrow(ProviderNotConfigured);
  });

  it("warms and caches the OAuth token without calling generateContent", async () => {
    const { account } = await testAccount();
    const google = fakeGoogle(OK_REPLY);
    const provider = new VertexProvider(
      account,
      "course-project",
      "global",
      "gemini-3.5-flash-lite",
      ["pressure", "spacing", "lateral"],
      0,
      google.fetcher,
    );
    expect(await provider.warm(AbortSignal.timeout(1000))).toBe(true);
    expect(google.calls).toHaveLength(1);
    expect(google.calls[0].url).toContain("oauth2.googleapis.com");
    expect(google.calls.some((c) => c.url.includes("generateContent"))).toBe(false);

    const result = await provider.propose(buildPrompt(SUMMARY, []), SUMMARY, AbortSignal.timeout(1000));
    expect(google.calls.filter((c) => c.url.includes("oauth2")).length).toBe(1);
    expect(google.calls.filter((c) => c.url.includes("generateContent")).length).toBe(1);
    expect(result.resolvedModel).toBe("gemini-3.5-flash-lite-001");
  });

  it("fails safe when warm encounters an HTTP error or missing config", async () => {
    const { account } = await testAccount();
    const calls: Call[] = [];
    const failingFetcher = async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return new Response("service unavailable", { status: 503 });
    };
    const provider = new VertexProvider(
      account,
      "course-project",
      "global",
      "gemini-3.5-flash-lite",
      ["pressure", "spacing", "lateral"],
      0,
      failingFetcher,
    );
    await expect(provider.warm(AbortSignal.timeout(1000))).rejects.toThrow("HTTP 503");
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toContain("oauth2.googleapis.com");

    const vertexEnv = {
      PROVIDER: "vertex",
      GOOGLE_CLOUD_PROJECT: "course-project",
      GOOGLE_CLOUD_LOCATION: "global",
      MODEL: "gemini-3.5-flash-lite",
      GCP_SERVICE_ACCOUNT_JSON: JSON.stringify(account),
    } as Env;
    expect(await warmProvider(vertexEnv, AbortSignal.timeout(1000), failingFetcher)).toBe(false);
    expect(calls.every((c) => !c.url.includes("generateContent"))).toBe(true);
    expect(await warmProvider({ PROVIDER: "vertex" } as Env)).toBe(false);
    expect(await warmProvider({ PROVIDER: "fixture" } as Env)).toBe(false);

    // Failed warm-up never caches a broken token, so a subsequent healthy propose still succeeds.
    const healthy = fakeGoogle(OK_REPLY);
    const recovered = new VertexProvider(
      account,
      "course-project",
      "global",
      "gemini-3.5-flash-lite",
      ["pressure", "spacing", "lateral"],
      0,
      healthy.fetcher,
    );
    const result = await recovered.propose(buildPrompt(SUMMARY, []), SUMMARY, AbortSignal.timeout(1000));
    expect(result.resolvedModel).toBe("gemini-3.5-flash-lite-001");
    expect(healthy.calls.filter((c) => c.url.includes("oauth2")).length).toBe(1);
  });
});

