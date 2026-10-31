import { createFileRoute, Link } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Camera, Upload } from "lucide-react";
import { AppShell, Card, SignInGate } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFacilities, imageFor, mad } from "@/lib/data";
import { metaBackendConfigured, metaVisionAnalyze, type VisionResult } from "@/lib/meta";

export const Route = createFileRoute("/ops")({
  head: () => ({ meta: [{ title: "Operations — ParkSpot AI" }, { name: "description", content: "Partner and admin operations for parking facilities." }, { property: "og:title", content: "Operations — ParkSpot AI" }, { property: "og:description", content: "Manage facility availability." }] }),
  component: Ops,
});

function VisionPanel() {
  const { t } = useI18n();
  const [result, setResult] = useState<(VisionResult & { simulated: boolean }) | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  if (!metaBackendConfigured()) {
    return (
      <Card>
        <p className="flex items-center gap-2 font-semibold"><Camera className="h-4 w-4" />{t("visionTitle")}</p>
        <p className="mt-1 text-sm text-muted-foreground">{t("visionUnavailable")}</p>
      </Card>
    );
  }

  const analyze = async (blob: Blob, simulated: boolean) => {
    setBusy(true);
    try {
      const out = await metaVisionAnalyze(blob, undefined, { simulated });
      setResult({ ...out, simulated }); // backend labels real uploads; the demo image is labeled simulated here
    } catch (e) {
      toast.error((e as Error).message);
      setResult(null);
    } finally { setBusy(false); }
  };

  const runSimulated = async () => {
    const blob = await (await fetch(imageFor("garage"))).blob();
    await analyze(blob, true);
  };

  return (
    <Card>
      <p className="flex items-center gap-2 font-semibold"><Camera className="h-4 w-4" />{t("visionTitle")}</p>
      <p className="mt-1 text-sm text-muted-foreground">{t("visionBody")}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button disabled={busy} onClick={() => fileRef.current?.click()} className="flex h-10 items-center gap-2 rounded-full border px-3 text-sm font-medium disabled:opacity-50">
          <Upload className="h-4 w-4" />{t("uploadFrame")} · {t("cameraReal")}
        </button>
        <button disabled={busy} onClick={() => void runSimulated()} className="h-10 rounded-full bg-secondary px-3 text-sm font-medium text-secondary-foreground disabled:opacity-50">
          {t("analyzeFrame")} · {t("cameraSim")}
        </button>
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void analyze(f, false); e.target.value = ""; }} />
      </div>
      {result && (
        <div className="mt-3 space-y-1 rounded-2xl bg-secondary/60 p-3 text-sm">
          <p className="text-xs font-medium text-muted-foreground">{result.simulated ? t("cameraSim") : t("cameraReal")}</p>
          <p>{t("vehiclesDetected")}: <b>{result.vehicles_detected}</b></p>
          <p>{t("plateRead")}: <b>{result.plate ?? t("plateNotRead")}</b></p>
          <p>{t("ocrConfidence")}: <b>{Math.round(result.ocr_confidence * 100)}%</b></p>
          <p className={result.access === "booking_verified" ? "font-semibold text-primary" : "font-semibold text-destructive"}>
            {result.access === "booking_verified" ? t("accessVerified") : t("accessNotGranted")}
          </p>
        </div>
      )}
    </Card>
  );
}

function Ops() {
  const { user, roles, loading } = useAuth();
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const { data: facilities = [] } = useFacilities();
  const allowed = roles.includes("admin") || roles.includes("partner");
  const { data: bookings = [] } = useQuery({ queryKey: ["ops-bookings"], enabled: allowed, queryFn: async () => (await supabase.from("bookings").select("id,total_cents,status,start_at,facility_id").order("created_at", { ascending: false }).limit(50)).data ?? [] });
  const [edit, setEdit] = useState<Record<string, string>>({});

  if (loading) return <AppShell back title={t("ops")}><div /></AppShell>;
  if (!user) return <AppShell back title={t("ops")}><SignInGate /></AppShell>;
  if (!allowed) return <AppShell back title={t("ops")}><p className="p-5 text-muted-foreground">Access restricted to partners and admins.</p></AppShell>;

  const revenue = bookings.filter((b) => b.status === "confirmed").reduce((s, b) => s + Number(b.total_cents), 0);
  const update = async (id: string, capacity: number) => {
    const v = Math.max(0, Math.min(capacity, Number(edit[id])));
    const { error } = await supabase.from("facilities").update({ available: v }).eq("id", id);
    if (error) { toast.error(error.message); return; }
    toast.success(t("saved")); qc.invalidateQueries({ queryKey: ["facilities"] });
  };
  return (
    <AppShell back title={t("ops")}>
      <div className="space-y-4 p-5">
        <div className="grid grid-cols-2 gap-3">
          <Card><p className="text-xs text-muted-foreground">{t("bookings")}</p><p className="text-2xl font-bold">{bookings.length}</p></Card>
          <Card><p className="text-xs text-muted-foreground">Revenue</p><p className="text-xl font-bold text-primary">{mad(revenue, lang)}</p></Card>
        </div>
        {roles.includes("admin") && (
          <Link to="/admin" className="block">
            <Card className="flex items-center justify-between">
              <p className="font-semibold">{t("adminTitle")}</p>
              <span className="text-sm font-medium text-primary">{t("aOverview")}</span>
            </Card>
          </Link>
        )}
        <VisionPanel />
        {facilities.map((f) => {
          // Partners may correct live availability, but never beyond the
          // facility's authorized capacity (falls back to legacy capacity
          // on a pre-0001 database where the column does not exist yet).
          const authorized = (f as { authorized_capacity?: number }).authorized_capacity ?? f.capacity;
          return (
          <Card key={f.id} className="flex items-center gap-3">
            <div className="flex-1"><p className="font-semibold">{f.name}</p><p className="text-xs text-muted-foreground">{t("authorizedCapacityLbl")}: {authorized}</p></div>
            <input type="number" min={0} max={authorized} defaultValue={f.available} onChange={(e) => setEdit({ ...edit, [f.id]: e.target.value })} className="h-10 w-20 rounded-xl border bg-background px-2 text-center" />
            <button onClick={() => update(f.id, authorized)} className="h-10 rounded-full bg-primary px-3 text-sm font-semibold text-primary-foreground">{t("update")}</button>
          </Card>
          );
        })}
      </div>
    </AppShell>
  );
}
