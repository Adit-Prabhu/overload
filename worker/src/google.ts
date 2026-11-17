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

let cached: CachedToken | null = null;

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
  const assertion = await signedAssertion(account, Math.floor(now() / 1000));
  const response = await fetcher(account.token_uri ?? DEFAULT_TOKEN_URI, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer",
      assertion,
    }).toString(),
    signal,
  });
  if (!response.ok) throw new Error(`token exchange failed with HTTP ${response.status}`);
  const body = (await response.json()) as { access_token?: string; expires_in?: number };
  if (!body.access_token) throw new Error("token exchange returned no access_token");
  cached = {
    email: account.client_email,
    token: body.access_token,
    expiresAt: now() + (body.expires_in ?? 3600) * 1000,
  };
  return cached.token;
}

export function forgetToken(): void {
  cached = null;
}
