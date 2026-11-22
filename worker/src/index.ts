// Overload rival service.
//   GET  /health                         liveness and configured provider
//   POST /warmup                         pre-warm the provider's OAuth token (no model call)
//   POST /sessions                       start a session, returns an opaque session_id
//   POST /sessions/:id/tactic            propose the Regulator's next protocol
// The game validates every response again and falls back to the neutral tactic itself.

import { getAgentByName } from "agents";
import { warmProvider } from "./providers";
import { TacticRequest } from "./schema";

export { BudgetLedger } from "./budget";
export { RivalSession } from "./session";

const TACTIC_PATH = /^\/sessions\/([0-9a-f-]{36})\/tactic$/;

function json(body: unknown, status = 200): Response {
  return Response.json(body, { status });
}

export default {
  async fetch(request: Request, env: Env, ctx?: ExecutionContext): Promise<Response> {
    try {
      return await route(request, env, ctx);
    } catch {
      // A session object that could not start or answer. Labelled, so the trace says the
      // service failed, and the game falls back to the neutral tactic (http_503).
      return json({ error: "internal_error" }, 503);
    }
  },
} satisfies ExportedHandler<Env>;

async function route(request: Request, env: Env, ctx?: ExecutionContext): Promise<Response> {
  const url = new URL(request.url);
  if (request.method === "GET" && url.pathname === "/health") {
    return json({ ok: true, service: "overload-rival", provider: env.PROVIDER ?? "fixture" });
  }
  if (request.method === "POST" && url.pathname === "/warmup") {
    const warmed = await warmProvider(env);
    return json({ ok: true, warmed, provider: env.PROVIDER ?? "fixture" });
  }
  if (request.method === "POST" && url.pathname === "/sessions") {
    const sessionId = crypto.randomUUID();
    const session = await getAgentByName(env.RIVAL_SESSION, sessionId);
    await session.begin();
    ctx?.waitUntil(warmProvider(env).catch(() => false));
    return json({ session_id: sessionId }, 201);
  }
  const match = TACTIC_PATH.exec(url.pathname);
  if (request.method === "POST" && match) {
    const body = await request.json().catch(() => null);
    const parsed = TacticRequest.safeParse(body);
    if (!parsed.success) {
      const issues = parsed.error.issues.map((i) => `${i.path.join(".") || "body"}: ${i.message}`);
      return json({ error: "invalid_request", issues }, 400);
    }
    const session = await getAgentByName(env.RIVAL_SESSION, match[1]);
    if (!(await session.isStarted())) return json({ error: "unknown_session" }, 404);
    return json(await session.propose(parsed.data, match[1]));
  }
  return json({ error: "not_found" }, 404);
}
