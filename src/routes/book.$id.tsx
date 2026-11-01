import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { AppShell, Card, SignInGate } from "@/components/AppShell";
import { useFacilities, useWallet, mad, errCode, imageFor } from "@/lib/data";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/book/$id")({
  head: () => ({
    meta: [
      { title: "Review & pay — ParkSpot AI" },
      { name: "description", content: "Review your parking reservation and pay with your wallet." },
      { property: "og:title", content: "Review & pay — ParkSpot AI" },
      { property: "og:description", content: "Pay for parking with ParkSpot Wallet." },
    ],
  }),
  component: BookPage,
});

function defaultStart() {
  const d = new Date(Date.now() + 3 * 3600_000);
  d.setMinutes(0, 0, 0);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:00`;
}

function BookPage() {
  const { id } = Route.useParams();
  const { t, lang } = useI18n();
  const { user, loading } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: facilities = [] } = useFacilities();
  const { data: wallet } = useWallet(user?.id);
  const f = facilities.find((x) => x.id === id);
  const [start, setStart] = useState(defaultStart);
  const [hours, setHours] = useState(2);
  const [busy, setBusy] = useState(false);
  const idem = useMemo(() => crypto.randomUUID(), [start, hours]);

  if (loading)
    return (
      <AppShell back title={t("reviewPay")}>
        <div />
      </AppShell>
    );
  if (!user)
    return (
      <AppShell back title={t("reviewPay")}>
        <SignInGate />
      </AppShell>
    );
  if (!f)
    return (
      <AppShell back title={t("reviewPay")}>
        <div className="m-5 h-40 animate-pulse rounded-3xl bg-card" />
      </AppShell>
    );

  const total = f.price_per_hour_cents * hours;
  const balance = Number(wallet?.available_cents ?? 0);
  const short = Math.max(0, total - balance);

  const pay = async () => {
    setBusy(true);
    const { data, error } = await supabase.rpc("create_booking", {
      p_facility_id: f.id,
      p_start_at: new Date(start).toISOString(),
      p_hours: hours,
      p_idempotency_key: idem,
    });
    setBusy(false);
    qc.invalidateQueries();
    if (error) {
      const e = errCode(error);
      if (e.code === "INSUFFICIENT_FUNDS") toast.error(t("insufficient"));
      else if (e.code === "FACILITY_FULL") toast.error(t("facilityFull"));
      else if (e.code === "FACILITY_INACTIVE") toast.error(t("facilityInactive"));
      else toast.error(e.code);
      return;
    }
    nav({ to: "/booking/$id", params: { id: data.id } });
  };

  return (
    <AppShell back title={t("reviewPay")}>
      <div className="space-y-4 p-5">
        <Card className="flex gap-3 p-3">
          <img src={imageFor(f.image_key)} alt="" className="h-20 w-24 rounded-2xl object-cover" />
          <div>
            <p className="font-semibold">{lang === "ar" ? f.name_ar : f.name}</p>
            <p className="text-xs text-muted-foreground">
              {f.address}, {f.city}
            </p>
            <p className="mt-1 text-sm font-bold text-primary">
              {mad(f.price_per_hour_cents, lang)} {t("perHour")}
            </p>
          </div>
        </Card>
        <Card className="space-y-4">
          <label className="block text-sm font-medium">
            {t("start")}
            <input
              type="datetime-local"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="mt-1 h-11 w-full rounded-2xl border bg-background px-3"
            />
          </label>
          <div>
            <p className="text-sm font-medium">{t("duration")}</p>
            <div className="mt-2 grid grid-cols-5 gap-2">
              {[1, 2, 3, 4, 8].map((h) => (
                <button
                  key={h}
                  onClick={() => setHours(h)}
                  className={`h-10 rounded-2xl border text-sm font-semibold ${hours === h ? "border-primary bg-primary text-primary-foreground" : "bg-background"}`}
                >
                  {h}h
                </button>
              ))}
            </div>
          </div>
        </Card>
        <Card className="space-y-2 text-sm">
          <Row
            k={`${mad(f.price_per_hour_cents, lang)} × ${hours} ${t("hours")}`}
            v={mad(total, lang)}
          />
          <Row k={t("total")} v={mad(total, lang)} bold />
          <hr />
          <Row k={t("available")} v={mad(balance, lang)} />
          {short === 0 && <Row k={t("after")} v={mad(balance - total, lang)} />}
        </Card>
        {short > 0 ? (
          <div className="rounded-3xl border border-destructive/30 bg-destructive/5 p-4">
            <p className="font-semibold text-destructive">{t("insufficient")}</p>
            <p className="mt-1 text-sm">{t("needMore", { x: mad(short, lang) })}</p>
            <Link
              to="/topup"
              search={{ amount: Math.ceil(short / 100), returnTo: `/book/${f.id}` }}
              className="mt-3 flex h-11 items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground"
            >
              {t("addMoney")}
            </Link>
          </div>
        ) : (
          <button
            disabled={busy}
            onClick={pay}
            className="h-12 w-full rounded-full bg-primary font-semibold text-primary-foreground shadow-lift disabled:opacity-60"
          >
            {t("payWallet")} · {mad(total, lang)}
          </button>
        )}
        <p className="text-center text-xs text-muted-foreground">{t("refundPolicy")}</p>
      </div>
    </AppShell>
  );
}

function Row({ k, v, bold }: { k: string; v: string; bold?: boolean }) {
  return (
    <div className={`flex justify-between ${bold ? "text-base font-bold" : ""}`}>
      <span className={bold ? "" : "text-muted-foreground"}>{k}</span>
      <span>{v}</span>
    </div>
  );
}
