import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Loader2, MapPin, Mic, Search, Sparkles, Square, Wallet, X } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { FacilityCard } from "@/components/FacilityCard";
import { useFacilities, useWallet, mad } from "@/lib/data";
import { GeoError, formatDistance, getCurrentPositionOnce, haversineMeters } from "@/lib/geo";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";
import { fetchMetaStatus, metaBackendConfigured, metaTranscribe, voiceMaxSeconds } from "@/lib/meta";

export const Route = createFileRoute("/home")({
  head: () => ({ meta: [{ title: "Discover parking — ParkSpot AI" }, { name: "description", content: "Browse parking facilities with live availability and prices in MAD." }, { property: "og:title", content: "Discover parking — ParkSpot AI" }, { property: "og:description", content: "Live parking availability across Morocco." }] }),
  component: HomePage,
});

const cities = ["All", "Casablanca", "Rabat", "Marrakech", "Tangier"];

function HomePage() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const { data = [], isLoading } = useFacilities();
  const { data: wallet } = useWallet(user?.id);
  const [q, setQ] = useState("");
  const [city, setCity] = useState("All");
  const [coords, setCoords] = useState<{ lat: number; lng: number } | null>(null);
  const [radiusKm, setRadiusKm] = useState(5);
  const [locBusy, setLocBusy] = useState(false);
  const [locNote, setLocNote] = useState<string | null>(null);

  // ---- voice search state
  const { data: metaStatus } = useQuery({ queryKey: ["meta-status"], queryFn: fetchMetaStatus, enabled: metaBackendConfigured(), retry: false });
  const voiceEnabled = metaStatus?.voice === "enabled";
  const maxRecordS = voiceMaxSeconds(metaStatus);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [transcribing, setTranscribing] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const cancelRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  const stopTimer = () => { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; } };

  const startRecording = async () => {
    if (!voiceEnabled) {
      // Say exactly which link in the chain is missing instead of a generic error.
      if (!metaBackendConfigured()) toast.error(t("voiceBackendMissing"));
      else if (metaStatus && !metaStatus.voice_flag_on) toast.error(t("voiceServerOff"));
      else if (metaStatus && !metaStatus.voice_key_present) toast.error(t("voiceKeyMissing"));
      else toast.error(t("voiceUnsupported"));
      return;
    }
    try {
      if (!navigator.mediaDevices?.getUserMedia) { toast.error(t("micInsecure")); return; }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      chunksRef.current = [];
      cancelRef.current = false;
      rec.ondataavailable = (e) => chunksRef.current.push(e.data);
      rec.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        stopTimer(); setRecording(false);
        if (cancelRef.current) return;
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
        if (!blob.size) return;
        setTranscribing(true);
        try {
          const { text } = await metaTranscribe(blob, lang);
          setQ(text); // transcript lands in the search field — editable before searching
          setCoords(null);
          // "near me" spoken → run the GPS flow (permission still requested explicitly by the browser)
          if (/near me|قريب مني|قريبة مني|près de moi|proche de moi/i.test(text)) void findNearMe();
        } catch (e) {
          toast.error((e as Error).message);
        } finally { setTranscribing(false); }
      };
      recorderRef.current = rec;
      rec.start(); setRecording(true); setElapsed(0);
      timerRef.current = setInterval(() => {
        setElapsed((s) => {
          if (s + 0.25 >= maxRecordS) { recorderRef.current?.stop(); return s; }
          return s + 0.25;
        });
      }, 250);
    } catch {
      toast.error(t("voiceUnsupported"));
    }
  };

  const cancelRecording = () => { cancelRef.current = true; recorderRef.current?.stop(); };

  // ---- GPS nearby
  const findNearMe = async () => {
    setLocBusy(true); setLocNote(null);
    toast(t("locationNeeded"));
    try {
      const pos = await getCurrentPositionOnce();
      setCoords({ lat: pos.lat, lng: pos.lng });
      setRadiusKm(5);
    } catch (e) {
      const kind = e instanceof GeoError ? e.kind : "unavailable";
      setLocNote(t(kind === "denied" ? "locationDenied" : kind === "timeout" ? "locationTimeout" : kind === "insecure" ? "locationInsecure" : kind === "unavailable" ? "locationUnavailable" : "locationUnsupported"));
    } finally { setLocBusy(false); }
  };

  const withDistance = useMemo(() => {
    if (!coords) return null;
    return data
      .map((f) => ({ f, d: haversineMeters(coords.lat, coords.lng, Number(f.lat), Number(f.lng)) }))
      .filter((x) => Number.isFinite(x.d))
      .sort((a, b) => a.d - b.d);
  }, [data, coords]);

  const list = useMemo(() => {
    if (withDistance) return withDistance.filter((x) => x.d <= radiusKm * 1000);
    return data
      .filter((f) => (city === "All" || f.city === city) &&
        (`${f.name} ${f.name_ar} ${f.city} ${f.address}`.toLowerCase().includes(q.toLowerCase())))
      .map((f) => ({ f, d: undefined as number | undefined }));
  }, [data, q, city, withDistance, radiusKm]);

  return (
    <AppShell>
      <section className="bg-brand px-5 pb-16 pt-6 text-primary-foreground">
        <p className="text-sm opacity-80">{t("tagline")}</p>
        <h1 className="mt-1 font-display text-3xl font-semibold">{t("hello")}</h1>
        <div className="mt-5 flex items-center gap-2">
          <label className="flex flex-1 items-center gap-2 rounded-full bg-card px-4 py-3 text-foreground shadow-soft">
            <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
            <input value={q} onChange={(e) => { setQ(e.target.value); setCoords(null); }} placeholder={t("search")} className="w-full bg-transparent text-sm outline-none" />
          </label>
          <button type="button" onClick={() => void startRecording()} disabled={recording || transcribing}
            aria-label={t("voiceSearch")} title={t("voiceSearch")}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-soft transition-transform active:scale-95 disabled:opacity-60">
            {transcribing ? <Loader2 className="h-5 w-5 animate-spin" /> : <Mic className="h-5 w-5" />}
          </button>
        </div>
        {recording && (
          <div className="mt-3 flex items-center gap-3 rounded-full bg-card/95 py-2 pe-2 ps-4 text-sm text-foreground shadow-soft">
            <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-destructive" />
            <span className="font-medium">{t("recording")} {Math.floor(elapsed)}s / {maxRecordS}s</span>
            <span className="flex-1" />
            <button type="button" onClick={() => recorderRef.current?.stop()} className="flex h-8 items-center gap-1 rounded-full bg-primary px-3 text-xs font-semibold text-primary-foreground">
              <Square className="h-3 w-3" />{t("stopRecording")}
            </button>
            <button type="button" onClick={cancelRecording} aria-label={t("cancel")} className="flex h-8 w-8 items-center justify-center rounded-full border">
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
        {transcribing && <p className="mt-3 text-sm opacity-90">{t("transcribing")}</p>}
        <button type="button" onClick={() => void findNearMe()} disabled={locBusy}
          className="mt-3 flex w-full items-center justify-center gap-2 rounded-full bg-primary py-3 text-sm font-semibold text-primary-foreground shadow-soft transition-transform active:scale-[0.99] disabled:opacity-60">
          {locBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <MapPin className="h-4 w-4" />}
          {t("parkingNearMe")}
        </button>
        {coords && <p className="mt-2 text-center text-xs opacity-90">● {t("nearYourLocation")} · {radiusKm} km</p>}
        {locNote && <p className="mt-2 rounded-2xl bg-card/95 p-3 text-center text-xs text-foreground">{locNote}</p>}
      </section>
      <div className="-mt-10 grid grid-cols-2 gap-3 px-5">
        <Link to="/wallet" className="rounded-3xl border bg-card p-4 shadow-soft">
          <Wallet className="h-5 w-5 text-primary" />
          <p className="mt-2 text-xs text-muted-foreground">{t("wallet")}</p>
          <p className="font-bold">{user ? mad(wallet?.available_cents ?? 0, lang) : t("signIn")}</p>
        </Link>
        <Link to="/assistant" className="rounded-3xl border bg-card p-4 shadow-soft">
          <Sparkles className="h-5 w-5 text-primary-glow" />
          <p className="mt-2 text-xs text-muted-foreground">ParkSpot AI</p>
          <p className="font-bold">{t("assistant")}</p>
        </Link>
      </div>
      {!coords && (
        <div className="no-scrollbar mt-6 flex gap-2 overflow-x-auto px-5 pb-1">
          {cities.map((c) => (
            <button key={c} onClick={() => setCity(c)} className={`shrink-0 rounded-full border px-4 py-1.5 text-sm font-medium ${city === c ? "border-primary bg-primary text-primary-foreground" : "bg-card"}`}>{c}</button>
          ))}
        </div>
      )}
      <h2 className="mt-5 px-5 font-display text-xl font-semibold">{coords ? t("nearYourLocation") : t("nearby")}</h2>
      <div className="mt-3 space-y-4 px-5 pb-6">
        {isLoading && [0, 1].map((i) => <div key={i} className="h-60 animate-pulse rounded-3xl bg-card" />)}
        {coords && !isLoading && list.length === 0 && (
          <div className="rounded-3xl border bg-card p-4 text-center shadow-soft">
            <p className="text-sm text-muted-foreground">{t("noNearby", { x: formatDistance(radiusKm * 1000, lang) })}</p>
            {radiusKm < 50 && (
              <button onClick={() => setRadiusKm((r) => Math.min(50, r * 3))} className="mt-3 rounded-full bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground">
                {t("widenSearch")}
              </button>
            )}
          </div>
        )}
        {list.map(({ f, d }) => <FacilityCard key={f.id} f={f} distanceM={d} />)}
      </div>
    </AppShell>
  );
}
