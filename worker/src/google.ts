// Google access tokens for Vertex AI from a service account key, inside a Worker.
// A Worker cannot use a local gcloud login, so it signs a short-lived JWT with the service
// account's private key (WebCrypto, RS256) and exchanges it for an OAuth access token.
// The key arrives only as a Worker secret (GCP_SERVICE_ACCOUNT_JSON). It is never logged.

export interface ServiceAccount {
  client_email: string;
  private_key: string;
  token_uri?: string;
}

export type Fetcher = (input: string, init?: RequestInit) => Promise<Response>;

const SCOPE = "https://www.googleapis.com/auth/cloud-platform";
const DEFAULT_TOKEN_URI = "https://oauth2.googleapis.com/token";

function base64url(data: ArrayBuffer | Uint8Array | string): string {
  const bytes =
    typeof data === "string" ? new TextEncoder().encode(data) : new Uint8Array(data as ArrayBuffer);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function pemToDer(pem: string): ArrayBuffer {
  const body = pem.replace(/-----(BEGIN|END) PRIVATE KEY-----/g, "").replace(/\s+/g, "");
  const binary = atob(body);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

export function parseServiceAccount(json: string | undefined): ServiceAccount {
  if (!json) throw new Error("GCP_SERVICE_ACCOUNT_JSON is not set");
  const parsed = JSON.parse(json) as Partial<ServiceAccount>;
  if (!parsed.client_email || !parsed.private_key) {
    throw new Error("service account JSON needs client_email and private_key");
  }
  return parsed as ServiceAccount;
}

export async function signedAssertion(account: ServiceAccount, nowSeconds: number): Promise<string> {
  const header = base64url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claims = base64url(
    JSON.stringify({
      iss: account.client_email,
      scope: SCOPE,
      aud: account.token_uri ?? DEFAULT_TOKEN_URI,
      iat: nowSeconds,
      exp: nowSeconds + 3600,
    }),
  );
  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToDer(account.private_key),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(`${header}.${claims}`));
  return `${header}.${claims}.${base64url(signature)}`;
}

interface CachedToken {
  email: string;
  token: string;
  expiresAt: number;
}

const TOKEN_FETCH_CEILING_MS = 10_000;

interface InFlightToken {
  email: string;
  promise: Promise<string>;
  controller: AbortController;
  waiters: number;
  settled: boolean;
}

let cached: CachedToken | null = null;
let inFlight: InFlightToken | null = null;

function waitForFlight(flight: InFlightToken, signal?: AbortSignal): Promise<string> {
  if (signal?.aborted) {
    return Promise.reject(signal.reason);
  }
  flight.waiters += 1;
  let released = false;
  const release = (aborted: boolean) => {
    if (released) return;
    released = true;
    flight.waiters -= 1;
    if (aborted && flight.waiters === 0 && !flight.settled) {
      if (inFlight === flight) inFlight = null;
      flight.controller.abort(signal?.reason);
    }
  };
  if (!signal) {
    return flight.promise.finally(() => release(false));
  }
  return new Promise<string>((resolve, reject) => {
    const onAbort = () => {
      release(true);
      reject(signal.reason);
    };
    signal.addEventListener("abort", onAbort, { once: true });
    flight.promise.then(
      (value) => {
        signal.removeEventListener("abort", onAbort);
        release(false);
        resolve(value);
      },
      (error) => {
        signal.removeEventListener("abort", onAbort);
        release(false);
        reject(error);
      },
    );
  });
}

/** Access token for the service account, reused until a minute before it expires. */
export async function accessToken(
  account: ServiceAccount,
  fetcher: Fetcher,
  now: () => number = Date.now,
  signal?: AbortSignal,
): Promise<string> {
  if (cached && cached.email === account.client_email && cached.expiresAt - 60_000 > now()) {
    return cached.token;
  }
  if (signal?.aborted) {
    throw signal.reason;
  }
  if (inFlight && inFlight.email === account.client_email && !inFlight.controller.signal.aborted) {
    return waitForFlight(inFlight, signal);
  }
  const issuedAt = Math.floor(now() / 1000);
  const controller = new AbortController();
  const flight: InFlightToken = {
    email: account.client_email,
    promise: null as unknown as Promise<string>,
    controller,
    waiters: 0,
    settled: false,
  };
  // Decouple the shared fetch from any individual caller's shorter signal. It cancels only
  // when every attached waiter aborts, or when the safe ceiling elapses.
  const ceilingTimer = setTimeout(() => {
    if (!flight.settled) {
      if (inFlight === flight) inFlight = null;
      controller.abort(new DOMException("token exchange timed out", "TimeoutError"));
    }
  }, TOKEN_FETCH_CEILING_MS);
  const run = (async () => {
    try {
      const assertion = await signedAssertion(account, issuedAt);
      if (controller.signal.aborted) throw controller.signal.reason;
      const response = await fetcher(account.token_uri ?? DEFAULT_TOKEN_URI, {
        method: "POST",
        headers: { "content-type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
          assertion,
        }).toString(),
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`token exchange failed with HTTP ${response.status}`);
      const body = (await response.json()) as { access_token?: string; expires_in?: number };
      if (!body.access_token) throw new Error("token exchange returned no access_token");
      const entry: CachedToken = {
        email: account.client_email,
        token: body.access_token,
        expiresAt: now() + (body.expires_in ?? 3600) * 1000,
      };
      if (inFlight === flight) {
        cached = entry;
      }
      return entry.token;
    } finally {
      clearTimeout(ceilingTimer);
      flight.settled = true;
      if (inFlight === flight) {
        inFlight = null;
      }
    }
  })();
  flight.promise = run;
  inFlight = flight;
  void run.catch(() => undefined);
  return waitForFlight(flight, signal);
}

export function forgetToken(): void {
  cached = null;
  if (inFlight) {
    inFlight.controller.abort();
    inFlight = null;
  }
}
