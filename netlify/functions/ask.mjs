/**
 * Thin proxy between the browser demo and the Python RAG API.
 *
 * UNVERIFIED — written from the Netlify Functions API reference (2026-10-03); not run yet.
 * Verify by deploying and calling GET /api/health, then POST /api/ask.
 *
 * Why this file exists: the browser must never hold the LLM API key. This function runs on
 * Netlify's side, holds the key in an environment variable, and forwards only the question.
 *
 * Environment variables (Site configuration -> Environment variables):
 *   RAG_API_URL   e.g. https://my-rag-api.onrender.com      (no trailing slash)
 *   RAG_API_KEY   the key/password the Python API expects, if any
 *   DEMO_PASSWORD the passphrase visitors must type in the page
 *
 * If RAG_API_URL is not set, /api/health still answers 200 with backend_configured:false, so the
 * static page can be deployed first and wired to a backend later without touching this code.
 */

const BACKEND = (process.env.RAG_API_URL || "").replace(/\/+$/, "");
const BACKEND_KEY = process.env.RAG_API_KEY || "";
const DEMO_PASSWORD = process.env.DEMO_PASSWORD || "";

const json = (payload, status = 200) =>
  new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });

export default async (req, context) => {
  const path = new URL(req.url).pathname;

  if (path.endsWith("/health")) {
    return json({
      ok: true,
      backend_configured: Boolean(BACKEND),
      password_required: Boolean(DEMO_PASSWORD),
    });
  }

  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  // Shared passphrase: the page asks once and sends it back in a header.
  if (DEMO_PASSWORD && req.headers.get("x-demo-key") !== DEMO_PASSWORD) {
    return json({ error: "unauthorized" }, 401);
  }

  let body;
  try {
    body = await req.json();
  } catch {
    return json({ error: "body must be JSON" }, 400);
  }

  const pertanyaan = (body.q || body.pertanyaan || "").trim();
  const k = Math.min(Math.max(parseInt(body.k ?? 5, 10) || 5, 1), 10);
  if (pertanyaan.length < 3) return json({ error: "question too short" }, 422);

  if (!BACKEND) {
    return json(
      { error: "backend_not_configured", detail: "Set RAG_API_URL in the Netlify site settings." },
      503,
    );
  }

  try {
    const r = await fetch(`${BACKEND}/ask`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        ...(BACKEND_KEY ? { authorization: `Bearer ${BACKEND_KEY}` } : {}),
      },
      body: JSON.stringify({ pertanyaan, k }),
      signal: AbortSignal.timeout(55_000), // Netlify's synchronous limit is 60 s
    });
    const text = await r.text();
    if (!r.ok) return json({ error: "backend_error", status: r.status, detail: text.slice(0, 400) }, 502);
    return new Response(text, {
      status: 200,
      headers: { "content-type": "application/json", "cache-control": "no-store" },
    });
  } catch (e) {
    return json(
      { error: "backend_unreachable", detail: String(e).slice(0, 200) },
      504,
    );
  }
};

export const config = { path: ["/api/ask", "/api/health"] };
