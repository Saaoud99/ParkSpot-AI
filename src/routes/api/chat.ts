import { createFileRoute } from "@tanstack/react-router";
import { streamText } from "ai";
import { createOpenAI } from "@ai-sdk/openai";
import { createClient } from "@supabase/supabase-js";

type Msg = { role: "user" | "assistant"; content: string };

export const Route = createFileRoute("/api/chat")({
  server: {
    handlers: {
      POST: async ({ request }) => {
        const body = (await request.json().catch(() => null)) as { messages?: Msg[]; lang?: string } | null;
        const messages = (body?.messages ?? []).filter((m) => (m.role === "user" || m.role === "assistant") && typeof m.content === "string").slice(-12).map((m) => ({ role: m.role, content: m.content.slice(0, 2000) }));
        if (!messages.length) return new Response("No messages", { status: 400 });
        const apiKey = process.env['LOVABLE_API_KEY'];
        if (!apiKey) return new Response("AI not configured", { status: 500 });

        const sb = createClient(process.env['SUPABASE_URL']!, process.env['SUPABASE_PUBLISHABLE_KEY']!, { auth: { persistSession: false, autoRefreshToken: false } });
        const { data: fac } = await sb.from("facilities").select("name,city,address,price_per_hour_cents,available,capacity,features,rating");
        const facts = (fac ?? []).map((f) => `- ${f.name} (${f.city}, ${f.address}): ${(f.price_per_hour_cents / 100).toFixed(2)} MAD/h, ${f.available}/${f.capacity} free, features ${f.features.join("/")}, rating ${f.rating}`).join("\n");

        const provider = createOpenAI({
          baseURL: "https://ai.gateway.lovable.dev/v1",
          apiKey,
          headers: { "Lovable-API-Key": apiKey, "X-Lovable-AIG-SDK": "vercel-ai-sdk" },
        });
        const result = streamText({
          model: provider.responses("openai/gpt-6-astra"),
          providerOptions: {
            openai: { forceReasoning: true, reasoningEffort: "low", reasoningSummary: "auto", store: false, include: ["reasoning.encrypted_content"] },
          },
          system: `You are ParkSpot AI, a concise, friendly parking assistant for Morocco. Reply in ${body?.lang === "ar" ? "Arabic" : "the user's language"}. Use only these live facilities:\n${facts}\nWallet: prepaid MAD balance (currently demo mode, not real money). Refunds: full up to 2h before start, 50% until start, none after. Keep answers under 120 words.`,
          messages,
          abortSignal: request.signal,
        });
        return result.toTextStreamResponse();
      },
    },
  },
});
