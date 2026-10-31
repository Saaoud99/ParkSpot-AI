import { createFileRoute, Link } from "@tanstack/react-router";
import { Plus, Info } from "lucide-react";
import { AppShell, Card, SignInGate } from "@/components/AppShell";
import { TxRow } from "@/components/TxRow";
import { useWallet, useTransactions, mad } from "@/lib/data";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import logo from "@/assets/logo.png";

export const Route = createFileRoute("/wallet")({
  head: () => ({ meta: [{ title: "ParkSpot Wallet" }, { name: "description", content: "Your prepaid ParkSpot balance and transactions in MAD." }, { property: "og:title", content: "ParkSpot Wallet" }, { property: "og:description", content: "Top up and pay for parking in one tap." }] }),
  component: WalletPage,
});

function WalletPage() {
  const { user, loading } = useAuth();
  const { t, lang } = useI18n();
  const { data: w } = useWallet(user?.id);
  const { data: tx = [] } = useTransactions(user?.id, 5);
  if (loading) return <AppShell title={t("wallet")}><div /></AppShell>;
  if (!user) return <AppShell title={t("wallet")}><SignInGate /></AppShell>;
  return (
    <AppShell title={t("wallet")}>
      <div className="space-y-4 p-5">
        <div className="relative overflow-hidden rounded-[2rem] bg-brand p-6 text-primary-foreground shadow-lift">
          <img src={logo} alt="" className="absolute -bottom-6 h-36 w-36 opacity-15 ltr:-right-6 rtl:-left-6" />
          <div className="flex items-center justify-between">
            <p className="text-sm opacity-80">{t("available")}</p>
            <span className="rounded-full bg-card/20 px-2.5 py-0.5 text-[10px] font-bold tracking-wider">DEMO</span>
          </div>
          <p className="mt-2 font-display text-4xl font-semibold">{mad(w?.available_cents ?? 0, lang)}</p>
          <div className="mt-5 flex gap-6 text-sm">
            <div><p className="opacity-70">{t("reserved")}</p><p className="font-semibold">{mad(w?.reserved_cents ?? 0, lang)}</p></div>
            <div><p className="opacity-70">{t("deposited")}</p><p className="font-semibold">{mad(w?.total_deposited_cents ?? 0, lang)}</p></div>
          </div>
        </div>
        <Link to="/topup" search={{}} className="flex h-12 items-center justify-center gap-2 rounded-full bg-primary font-semibold text-primary-foreground shadow-lift"><Plus className="h-5 w-5" />{t("addMoney")}</Link>
        <p className="flex items-start gap-2 rounded-2xl bg-secondary p-3 text-xs text-secondary-foreground"><Info className="mt-0.5 h-4 w-4 shrink-0" />{t("demoNote")}</p>
        <Card>
          <div className="flex items-center justify-between"><h2 className="font-semibold">{t("recent")}</h2><Link to="/transactions" className="text-sm font-semibold text-primary">{t("seeAll")}</Link></div>
          {tx.length === 0 ? <p className="py-6 text-center text-sm text-muted-foreground">{t("noTx")}</p> : <div className="divide-y">{tx.map((x) => <TxRow key={x.id} tx={x} />)}</div>}
        </Card>
      </div>
    </AppShell>
  );
}
