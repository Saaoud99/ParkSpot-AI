import { createFileRoute, Link } from "@tanstack/react-router";
import { MapPin, Star, Zap, Shield, Umbrella, Car, Clock } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { useFacilities, imageFor, mad } from "@/lib/data";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/facility/$id")({
  head: () => ({ meta: [{ title: "Parking facility — ParkSpot AI" }, { name: "description", content: "Facility details, prices and availability." }, { property: "og:title", content: "Parking facility — ParkSpot AI" }, { property: "og:description", content: "Book this parking spot with ParkSpot Wallet." }] }),
  component: FacilityPage,
});

const featIcon: Record<string, typeof Zap> = { ev: Zap, cctv: Shield, covered: Umbrella, valet: Car };
const featLabel: Record<string, string> = { ev: "EV charging", cctv: "CCTV 24/7", covered: "Covered", valet: "Valet" };

function FacilityPage() {
  const { id } = Route.useParams();
  const { t, lang } = useI18n();
  const { data = [], isLoading } = useFacilities();
  const f = data.find((x) => x.id === id);
  if (isLoading) return <AppShell back><div className="m-5 h-64 animate-pulse rounded-3xl bg-card" /></AppShell>;
  if (!f) return <AppShell back><p className="p-5">Not found</p></AppShell>;
  const pct = Math.round((f.available / Math.max(1, f.capacity)) * 100);
  return (
    <AppShell back title={lang === "ar" ? f.name_ar : f.name}>
      <img src={imageFor(f.image_key)} alt={f.name} className="h-64 w-full object-cover" />
      <div className="-mt-6 rounded-t-[2rem] bg-background px-5 pt-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-display text-2xl font-semibold">{lang === "ar" ? f.name_ar : f.name}</h1>
            <p className="mt-1 flex items-center gap-1 text-sm text-muted-foreground"><MapPin className="h-4 w-4" />{f.address}, {f.city}</p>
          </div>
          <span className="flex items-center gap-1 rounded-full bg-secondary px-3 py-1 text-sm font-semibold"><Star className="h-4 w-4 fill-warning text-warning" />{f.rating}</span>
        </div>
        <div className="mt-5 grid grid-cols-3 gap-3 text-center">
          <div className="rounded-2xl border bg-card p-3"><p className="text-xs text-muted-foreground">{t("perHour")}</p><p className="font-bold text-primary">{mad(f.price_per_hour_cents, lang)}</p></div>
          <div className="rounded-2xl border bg-card p-3"><p className="text-xs text-muted-foreground">{t("availability")}</p><p className="font-bold">{f.available}/{f.capacity}</p></div>
          <div className="rounded-2xl border bg-card p-3"><Clock className="mx-auto h-4 w-4 text-primary" /><p className="text-xs font-semibold">{t("open24")}</p></div>
        </div>
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-secondary"><div className="h-full bg-primary" style={{ width: `${pct}%` }} /></div>
        <h2 className="mt-6 font-semibold">{t("features")}</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {f.features.map((k) => { const I = featIcon[k] ?? Shield; return <span key={k} className="flex items-center gap-1.5 rounded-full border bg-card px-3 py-1.5 text-sm"><I className="h-4 w-4 text-primary" />{featLabel[k] ?? k}</span>; })}
        </div>
        <p className="mt-6 text-xs text-muted-foreground">{t("refundPolicy")}</p>
        <div className="sticky bottom-4 mt-6 pb-4">
          {f.available > 0 ? (
            <Link to="/book/$id" params={{ id: f.id }} className="flex h-12 w-full items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground shadow-lift">{t("book")}</Link>
          ) : (
            <button disabled className="h-12 w-full rounded-full bg-muted font-semibold text-muted-foreground">{t("full")}</button>
          )}
        </div>
      </div>
    </AppShell>
  );
}
