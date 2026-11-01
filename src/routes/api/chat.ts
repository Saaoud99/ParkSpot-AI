import { createFileRoute } from "@tanstack/react-router";
import { createClient } from "@supabase/supabase-js";
import { groundedReply, type AssistantFacility } from "@/lib/assistantCore";

type Msg = { role: "user" | "assistant"; content: string };

/**
 * Always-available assistant fallback (no LLM, no API key).
 *
 * Answers deterministically from live public facility rows via
 * groundedReply() — it cannot invent facilities or prices. The primary
 * assistant is the FastAPI backend (Muse Spark when configured, grounded
 * mode otherwise); this route only serves sessions where that backend is
 * not connected. Rate-limited per IP because it is unauthenticated by
 * design (it only ever reads public inventory).
 */
const hits = new Map<string, number[]>();
function rateLimited(ip: string): boolean {
  const now = Date.now();
  const recent = (hits.get(ip) ?? []).filter((t) => now - t < 60_000);
  recent.push(now);
  hits.set(ip, recent);
  return recent.length > 30;
}

export const Route = createFileRoute("/api/chat")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const ip = request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "local";
        if (rateLimited(ip))
          return new Response("Too many requests. Please wait a moment.", { status: 429 });
        const body = (await request.json().catch(() => null)) as {
          messages?: Msg[];
          lang?: string;
        } | null;
        const messages = (body?.messages ?? [])
          .filter(
            (m) => (m.role === "user" || m.role === "assistant") && typeof m.content === "string",
          )
          .slice(-12)
          .map((m) => ({ role: m.role, content: m.content.slice(0, 2000) }));
        const lastUser = [...messages].reverse().find((m) => m.role === "user");
        if (!lastUser) return new Response("No messages", { status: 400 });

        const url = process.env["SUPABASE_URL"];
        const key = process.env["SUPABASE_PUBLISHABLE_KEY"];
        if (!url || !key)
          return new Response("Assistant inventory is not configured on this server.", {
            status: 503,
          });
        const sb = createClient(url, key, {
          auth: { persistSession: false, autoRefreshToken: false },
        });
        // select("*") on purpose: the generated types predate migration
        // 0001, and "*" returns `active` when the column exists (post-0001)
        // and simply omits it before — the filter below handles both.
        const { data, error } = await sb.from("facilities").select("*");
        if (error)
          return new Response("Could not load parking inventory right now.", { status: 502 });
        const facilities = ((data ?? []) as AssistantFacility[]).filter(
          (f) => (f as AssistantFacility & { active?: boolean }).active !== false,
        );
        const text = groundedReply(facilities, lastUser.content, body?.lang ?? "en");
        return new Response(text, { headers: { "content-type": "text/plain; charset=utf-8" } });
      },
    },
  },
});
