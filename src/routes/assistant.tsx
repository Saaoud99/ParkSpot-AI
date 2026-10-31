import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Mic, Send, Sparkles } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { FacilityCard, type Facility } from "@/components/FacilityCard";
import { useFacilities } from "@/lib/data";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { fetchMetaStatus, metaBackendConfigured, metaChat, metaTranscribe, voiceMaxSeconds } from "@/lib/meta";

export const Route = createFileRoute("/assistant")({
  head: () => ({ meta: [{ title: "AI Assistant — ParkSpot AI" }, { name: "description", content: "Ask ParkSpot AI where to park, prices and wallet questions." }, { property: "og:title", content: "AI Assistant — ParkSpot AI" }, { property: "og:description", content: "Your AI parking assistant." }] }),
  component: Assistant,
});

type Msg = { role: "user" | "assistant"; content: string; facilities?: Facility[] };

function Assistant() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const { data: allFacilities = [] } = useFacilities();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const recordTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const suggestions = [t("suggest1"), t("suggest2"), t("suggest3")];
  const { data: metaStatus } = useQuery({
    queryKey: ["meta-status"],
    queryFn: fetchMetaStatus,
    enabled: metaBackendConfigured(),
    retry: false,
  });
  const voiceEnabled = metaStatus?.voice === "enabled";
  // Backend assistant runs in one of two honestly-labeled modes: Muse Spark
  // when configured, otherwise the deterministic grounded-inventory mode.
  const [chatMode, setChatMode] = useState<string | null>(null);
  const useMeta = metaBackendConfigured() && !!user && (metaStatus?.assistant === "meta" || metaStatus?.assistant === "grounded_fallback");

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs]);

  const sendViaMeta = async (next: Msg[]) => {
    const out = await metaChat(next.map((m) => ({ role: m.role, content: m.content })), lang);
    setChatMode(out.mode ?? "meta");
    // Cards render only for facilities that exist in real inventory — never model-invented ones.
    const cards = out.facilities
      .map((f) => allFacilities.find((r) => r.id === f.id))
      .filter((f): f is Facility => !!f);
    setMsgs([...next, { role: "assistant", content: out.reply, facilities: cards }]);
  };

  const sendViaStream = async (next: Msg[]) => {
    setChatMode("grounded_fallback"); // /api/chat is the grounded engine — label it as such
    setMsgs([...next, { role: "assistant", content: "" }]);
    const res = await fetch("/api/chat", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ messages: next.map((m) => ({ role: m.role, content: m.content })), lang }) });
    if (!res.ok || !res.body) throw new Error((await res.text()) || `Error ${res.status}`);
    const reader = res.body.getReader(); const dec = new TextDecoder(); let acc = "";
    for (;;) {
      const { done, value } = await reader.read(); if (done) break;
      acc += dec.decode(value, { stream: true });
      setMsgs([...next, { role: "assistant", content: acc }]);
    }
    if (!acc) setMsgs([...next, { role: "assistant", content: "…" }]);
  };

  const send = async (text: string) => {
    if (!text.trim() || busy) return;
    const next: Msg[] = [...msgs, { role: "user", content: text.trim() }];
    setMsgs(next); setInput(""); setBusy(true);
    try {
      if (useMeta) await sendViaMeta(next); else await sendViaStream(next);
    } catch {
      // Honest degradation: no fake answers; manual search keeps working.
      setMsgs([...next, { role: "assistant", content: t("aiUnavailable") }]);
    } finally { setBusy(false); }
  };

  const toggleMic = async () => {
    if (recording) { recorderRef.current?.stop(); return; }
    try {
      if (!navigator.mediaDevices?.getUserMedia) return; // insecure origin (http LAN IP): mic unavailable
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks: BlobPart[] = [];
      rec.ondataavailable = (e) => chunks.push(e.data);
      rec.onstop = async () => {
        if (recordTimeoutRef.current) { clearTimeout(recordTimeoutRef.current); recordTimeoutRef.current = null; }
        stream.getTracks().forEach((tr) => tr.stop());
        setRecording(false);
        try {
          const { text } = await metaTranscribe(new Blob(chunks, { type: rec.mimeType || "audio/webm" }), lang);
          setInput(text);
        } catch { setInput(""); }
      };
      recorderRef.current = rec;
      rec.start(); setRecording(true);
      // Same backend-configured cap as Home (30 s safe default).
      recordTimeoutRef.current = setTimeout(() => recorderRef.current?.stop(), voiceMaxSeconds(metaStatus) * 1000);
    } catch { setRecording(false); }
  };

  return (
    <AppShell title={t("assistant")}>
      <div className="space-y-3 p-5 pb-24">
        <div className="flex gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand"><Sparkles className="h-4 w-4 text-primary-foreground" /></span>
          <div className="rounded-3xl rounded-ss-md border bg-card p-3 text-sm shadow-soft">{t("aiHello")}</div>
        </div>
        {(chatMode ?? metaStatus?.assistant) && (
          <p className="ps-12 text-[11px] font-medium text-muted-foreground">
            {(chatMode ?? metaStatus?.assistant) === "meta" ? t("aiModeMeta") : t("aiModeGrounded")}
          </p>
        )}
        {msgs.length === 0 && <div className="flex flex-wrap gap-2 ps-12">{suggestions.map((s) => <button key={s} onClick={() => void send(s)} className="rounded-full border bg-secondary px-3 py-1.5 text-xs font-medium text-secondary-foreground">{s}</button>)}</div>}
        {msgs.map((m, i) => (
          <div key={i}>
            <div className={`flex ${m.role === "user" ? "justify-end" : "gap-3"}`}>
              {m.role === "assistant" && <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand"><Sparkles className="h-4 w-4 text-primary-foreground" /></span>}
              <div className={`max-w-[80%] whitespace-pre-wrap rounded-3xl p-3 text-sm ${m.role === "user" ? "rounded-se-md bg-primary text-primary-foreground" : "rounded-ss-md border bg-card shadow-soft"}`}>
                {m.content || <span className="inline-flex gap-1"><span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground" /><span className="h-2 w-2 animate-bounce rounded-full bg-muted-foreground [animation-delay:120ms]" /></span>}
              </div>
            </div>
            {!!m.facilities?.length && (
              <div className="mt-2 space-y-3 ps-12">
                <p className="text-[11px] font-medium text-muted-foreground">{t("realAvailability")}</p>
                {m.facilities.map((f) => <FacilityCard key={f.id} f={f} compact />)}
              </div>
            )}
          </div>
        ))}
        <div ref={endRef} />
      </div>
      <form onSubmit={(e) => { e.preventDefault(); void send(input); }} className="absolute inset-x-0 bottom-[76px] z-20 flex gap-2 border-t bg-background p-3">
        <input value={input} onChange={(e) => setInput(e.target.value)} placeholder={recording ? t("listening") : t("askAI")} className="h-11 flex-1 rounded-full border bg-card px-4 text-sm outline-none focus:border-primary" />
        {voiceEnabled && (
          <button type="button" onClick={() => void toggleMic()} aria-label={t("mic")} className={`flex h-11 w-11 items-center justify-center rounded-full border ${recording ? "bg-destructive text-destructive-foreground" : "bg-card"}`}>
            <Mic className="h-4 w-4" />
          </button>
        )}
        <button disabled={busy} className="flex h-11 w-11 items-center justify-center rounded-full bg-primary text-primary-foreground disabled:opacity-50"><Send className="h-4 w-4 rtl:rotate-180" /></button>
      </form>
    </AppShell>
  );
}
