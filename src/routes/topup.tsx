import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { AppShell, Card, SignInGate } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { mad, useWallet } from "@/lib/data";

export const Route = createFileRoute("/topup")({
  validateSearch: z.object({ amount: z.number().optional(), returnTo: z.string().optional() }),
  head: () => ({ meta: [{ title: "Add money — ParkSpot Wallet" }, { name: "description", content: "Top up your ParkSpot Wallet (demo mode)." }, { property: "og:title", content: "Add money — ParkSpot Wallet" }, { property: "og:description", content: "Demo top-up for ParkSpot Wallet." }] }),
  component: TopUp,
});

const presets = [50, 100, 200, 500];

function TopUp() {
  const { amount, returnTo } = Route.useSearch();
  const { user, loading } = useAuth();
  const { t, lang } = useI18n();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { data: w } = useWallet(user?.id);
  const [value, setValue] = useState(String(amount ? Math.max(10, amount) : 100));
  const [outcome, setOutcome] = useState<"succeeded" | "failed" | "pending">("succeeded");
  const [step, setStep] = useState<"choose" | "review">("choose");
  const [busy, setBusy] = useState(false);
  const cents = Math.round(Number(value) * 100);
  const valid = Number.isFinite(cents) && cents >= 1000 && cents <= 500000;
  const idem = useMemo(() => crypto.randomUUID(), [cents, outcome, step]);

  if (loading) return <AppShell back title={t("addMoney")}><div /></AppShell>;
  if (!user) return <AppShell back title={t("addMoney")}><SignInGate /></AppShell>;

  const confirmTopup = async () => {
    setBusy(true);
    const { data, error } = await supabase.rpc("demo_topup", { p_amount_cents: cents, p_outcome: outcome, p_idempotency_key: idem });
    setBusy(false);
    qc.invalidateQueries();
    if (error) { toast.error(error.message); return; }
    if (data.status === "succeeded") {
      toast.success(`${t("topupDone")} · ${mad(cents, lang)}`);
      if (returnTo?.startsWith("/book/")) nav({ to: "/book/$id", params: { id: returnTo.slice(6) } });
      else nav({ to: "/wallet" });
    } else if (data.status === "failed") { toast.error(t("topupFailed")); setStep("choose"); }
    else { toast(t("topupPending")); nav({ to: "/transactions" }); }
  };

  return (
    <AppShell back title={t("addMoney")}>
      <div className="space-y-4 p-5">
        <p className="rounded-2xl bg-warning/15 p-3 text-xs font-medium">{t("demoNote")}</p>
        {step === "choose" ? (
          <>
            <Card>
              <p className="font-semibold">{t("chooseAmount")}</p>
              <div className="mt-3 grid grid-cols-4 gap-2">
                {presets.map((p) => <button key={p} onClick={() => setValue(String(p))} className={`h-11 rounded-2xl border text-sm font-semibold ${Number(value) === p ? "border-primary bg-primary text-primary-foreground" : "bg-background"}`}>{p}</button>)}
              </div>
              <label className="mt-4 block text-sm font-medium">{t("custom")}
                <input inputMode="decimal" value={value} onChange={(e) => setValue(e.target.value.replace(/[^\d.]/g, ""))} className="mt-1 h-12 w-full rounded-2xl border bg-background px-4 text-lg font-bold" />
              </label>
              {!valid && <p className="mt-2 text-xs text-destructive">10 – 5000 MAD</p>}
            </Card>
            <Card>
              <p className="font-semibold">{t("outcome")}</p>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {(["succeeded", "failed", "pending"] as const).map((o) => <button key={o} onClick={() => setOutcome(o)} className={`h-10 rounded-2xl border text-sm font-semibold ${outcome === o ? "border-primary bg-secondary text-primary" : "bg-background"}`}>{t(o)}</button>)}
              </div>
            </Card>
            <button disabled={!valid} onClick={() => setStep("review")} className="h-12 w-full rounded-full bg-primary font-semibold text-primary-foreground shadow-lift disabled:opacity-50">{t("review")}</button>
          </>
        ) : (
          <>
            <Card className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-muted-foreground">{t("topup")}</span><span className="font-bold">{mad(cents, lang)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">{t("outcome")}</span><span>DEMO · {t(outcome)}</span></div>
              <div className="flex justify-between"><span className="text-muted-foreground">{t("available")}</span><span>{mad(w?.available_cents ?? 0, lang)}</span></div>
            </Card>
            <button disabled={busy} onClick={confirmTopup} className="h-12 w-full rounded-full bg-primary font-semibold text-primary-foreground shadow-lift disabled:opacity-60">{t("confirmTopup")}</button>
            <button onClick={() => setStep("choose")} className="h-11 w-full rounded-full border font-semibold">←</button>
          </>
        )}
      </div>
    </AppShell>
  );
}
