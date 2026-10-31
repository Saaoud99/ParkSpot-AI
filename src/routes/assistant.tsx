import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { Send, Sparkles } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/assistant")({
  head: () => ({ meta: [{ title: "AI Assistant — ParkSpot AI" }, { name: "description", content: "Ask ParkSpot AI where to park, prices and wallet questions." }, { property: "og:title", content: "AI Assistant — ParkSpot AI" }, { property: "og:description", content: "Your AI parking assistant." }] }),
  component: Assistant,
});

type Msg = { role: "user" | "assistant"; content: string };
const suggestions = ["Cheapest parking in Casablanca?", "Where can I charge my EV?", "How do refunds work?"];

function Assistant() {
  const { t, lang } = useI18n();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    const next = [...msgs, { role: "user" as const, content: text.trim() }];
    setMsgs([...next, { role: "assistant", content: "" }]);
    setInput(""); setBusy(true);
    try {
      const res = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ messages: next, lang }) });
      if (!res.ok || !res.body) throw new Error(await res.text() || `Error ${res.status}`);
      const reader = res.body.getReader(); const dec = new TextDecoder(); let acc = "";
      for (;;) {
        const { done, value } = await reader.read(); if (done) break;
        acc += dec.decode(value, { stream: true });
        setMsgs([...next, { role: "assistant", content: acc }]);
        endRef.current?.scrollIntoView({ behavior: "smooth" });
      }
      if (!acc) setMsgs([...next, { role: "assistant", content: "…" }]);
    } catch (e) {
      setMsgs([...next, { role: "assistant", content: `⚠️ ${(e as Error).message}` }]);
    } finally { setBusy(false); }
  };

  return (
    <AppShell title={t("assistant")}>
      <div className="space-y-3 p-5 pb-24">
        <div className="flex gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand"><Sparkles className="h-4 w-4 text-primary-foreground" /></span>
          <div className="rounded-3xl rounded-ss-md border bg-card p-3 text-sm shadow-soft">{t("aiHello")}</div>
        </div>
        {msgs.length === 0 && <div className="flex flex-wrap gap-2 ps-12">{suggestions.map((s) => <button key={s} onClick={() => send(s)} className="rounded-full border bg-secondary px-3 py-1.5 text-xs font-medium text-secondary-foreground">{s}</button>)}</div>}
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "gap-3"}`}>
            {m.role === "assistant" && <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand"><Sparkles className="h-4 w-4 text-primary-foreground" /></span>}
            <div className={`max-w-[80%] whitespace-pre-wrap rounded-3xl p-3 text-sm ${m.role === "user" ? "rounded-se-md bg-primary text-primary-foreground" : "rounded-ss-md border bg-card shadow-soft"}`}>
              {m.content || <span className="inline-flex gap-1"><span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" /><span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:120ms]" /></span>}
            </div>
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); void send(input); }} className="absolute inset-x-0 bottom-[76px] z-20 flex gap-2 border-t bg-background p-3">
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={t("askAI")} className="h-11 flex-1 rounded-full border bg-card px-4 text-sm outline-none focus:border-primary" />
        <button disabled={busy} className="flex h-11 w-11 items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-50"><Send className="h-4 w-4 rtl:rotate-180" /></button>
      </form>
    </AppShell>
  );
}
