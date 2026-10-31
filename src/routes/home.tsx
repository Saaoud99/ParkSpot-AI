import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Search, Sparkles, Wallet } from "lucide-react";
import { AppShell } from "@/components/AppShell";
import { FacilityCard } from "@/components/FacilityCard";
import { useFacilities, useWallet, mad } from "@/lib/data";
import { useI18n } from "@/lib/i18n";
import { useAuth } from "@/lib/auth";

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
  const list = useMemo(() => data.filter((f) =>
    (city === "All" || f.city === city) &&
    (`${f.name} ${f.name_ar} ${f.city} ${f.address}`.toLowerCase().includes(q.toLowerCase()))), [data, q, city]);

  return (
    <AppShell>
      <section className="bg-brand px-5 pb-16 pt-6 text-primary-foreground">
        <p className="text-sm opacity-80">{t("tagline")}</p>
        <h1 className="mt-1 font-display text-3xl font-semibold">{t("hello")}</h1>
        <label className="mt-5 flex items-center gap-2 rounded-full bg-card px-4 py-3 text-foreground shadow-soft">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("search")} className="w-full bg-transparent text-sm outline-none" />
        </label>
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
      <div className="mt-6 flex gap-2 overflow-x-auto px-5 pb-1">
        {cities.map((c) => (
          <button key={c} onClick={() => setCity(c)} className={`shrink-0 rounded-full border px-4 py-1.5 text-sm font-medium ${city === c ? "border-primary bg-primary text-primary-foreground" : "bg-card"}`}>{c}</button>
        ))}
      </div>
      <h2 className="mt-5 px-5 font-display text-xl font-semibold">{t("nearby")}</h2>
      <div className="mt-3 space-y-4 px-5">
        {isLoading && [0, 1].map((i) => <div key={i} className="h-60 animate-pulse rounded-3xl bg-card" />)}
        {list.map((f) => <FacilityCard key={f.id} f={f} />)}
      </div>
    </AppShell>
  );
}
