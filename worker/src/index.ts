// Overload rival service. Scaffold: only GET /health exists.
// Sessions and POST /sessions/:id/tactic arrive in implementation plan task 4.

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "GET" && url.pathname === "/health") {
      return Response.json({ ok: true, service: "overload-rival", stage: "scaffold" });
    }
    return Response.json({ error: "not_found" }, { status: 404 });
  },
} satisfies ExportedHandler;
