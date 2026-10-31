import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { Car, Globe, LogOut, Settings2 } from "lucide-react";
import { AppShell, Card, SignInGate } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/profile")({
  head: () => ({ meta: [{ title: "Profile — ParkSpot AI" }, { name: "description", content: "Manage your profile, vehicle and language." }, { property: "og:title", content: "Profile — ParkSpot AI" }, { property: "og:description", content: "Your ParkSpot profile." }] }),
  component: Profile,
});

function Profile() {
  const { user, loading, roles } = useAuth();
  const { t, lang, setLang } = useI18n();
  const nav = useNavigate();
  const { data: p } = useQuery({ queryKey: ["profile", user?.id], enabled: !!user, queryFn: async () => (await supabase.from("profiles").select("*").eq("id", user!.id).single()).data });
  const [form, setForm] = useState({ display_name: "", phone: "", vehicle_plate: "", vehicle_model: "" });
  useEffect(() => { if (p) setForm({ display_name: p.display_name ?? "", phone: p.phone ?? "", vehicle_plate: p.vehicle_plate ?? "", vehicle_model: p.vehicle_model ?? "" }); }, [p]);

  const langToggle = (
    <Card className="flex items-center justify-between">
      <span className="flex items-center gap-2 font-medium"><Globe className="h-5 w-5 text-primary" />{t("language")}</span>
      <div className="flex rounded-full border p-1">
        {(["en", "ar"] as const).map((l) => <button key={l} onClick={() => setLang(l)} className={`rounded-full px-3 py-1 text-sm font-semibold ${lang === l ? "bg-primary text-primary-foreground" : ""}`}>{l === "en" ? "English" : "العربية"}</button>)}
      </div>
    </Card>
  );
  if (loading) return <AppShell title={t("profile")}><div /></AppShell>;
  if (!user) return <AppShell title={t("profile")}><SignInGate /><div className="px-5">{langToggle}</div></AppShell>;

  const save = async () => {
    const { error } = await supabase.from("profiles").update(form).eq("id", user.id);
    error ? toast.error(error.message) : toast.success(t("saved"));
  };
  const field = (k: keyof typeof form, label: string) => (
    <label className="block text-sm font-medium">{label}
      <input value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} className="mt-1 h-11 w-full rounded-2xl border bg-background px-3" />
    </label>
  );
  return (
    <AppShell title={t("profile")}>
      <div className="space-y-4 p-5">
        <div className="flex items-center gap-4">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand font-display text-2xl text-primary-foreground">{(form.display_name || user.email || "?")[0]?.toUpperCase()}</div>
          <div><p className="font-display text-xl font-semibold">{form.display_name || "—"}</p><p className="text-sm text-muted-foreground">{user.email}</p></div>
        </div>
        <Card className="space-y-3">{field("display_name", t("name"))}{field("phone", t("phone"))}</Card>
        <Card className="space-y-3">
          <p className="flex items-center gap-2 font-semibold"><Car className="h-5 w-5 text-primary" />{t("vehicle")}</p>
          {field("vehicle_plate", t("plate"))}{field("vehicle_model", t("model"))}
        </Card>
        <button onClick={save} className="h-12 w-full rounded-full bg-primary font-semibold text-primary-foreground">{t("save")}</button>
        {langToggle}
        {(roles.includes("admin") || roles.includes("partner")) && (
          <Link to="/ops" className="flex h-12 items-center justify-center gap-2 rounded-full border bg-card font-semibold"><Settings2 className="h-5 w-5" />{t("ops")}</Link>
        )}
        <button onClick={async () => { await supabase.auth.signOut(); nav({ to: "/home" }); }} className="flex h-12 w-full items-center justify-center gap-2 rounded-full border font-semibold text-destructive"><LogOut className="h-5 w-5" />{t("logout")}</button>
      </div>
    </AppShell>
  );
}
