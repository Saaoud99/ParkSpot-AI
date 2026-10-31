import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AppShell, Card, SignInGate } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useFacilities, mad } from "@/lib/data";

export const Route = createFileRoute("/ops")({
  head: () => ({ meta: [{ title: "Operations — ParkSpot AI" }, { name: "description", content: "Partner and admin operations for parking facilities." }, { property: "og:title", content: "Operations — ParkSpot AI" }, { property: "og:description", content: "Manage facility availability." }] }),
  component: Ops,
});

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
        {facilities.map((f) => (
          <Card key={f.id} className="flex items-center gap-3">
            <div className="flex-1"><p className="font-semibold">{f.name}</p><p className="text-xs text-muted-foreground">{t("capacity")}: {f.capacity}</p></div>
            <input type="number" min={0} max={f.capacity} defaultValue={f.available} onChange={(e) => setEdit({ ...edit, [f.id]: e.target.value })} className="h-10 w-20 rounded-xl border bg-background px-2 text-center" />
            <button onClick={() => update(f.id, f.capacity)} className="h-10 rounded-full bg-primary px-3 text-sm font-semibold text-primary-foreground">{t("update")}</button>
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
