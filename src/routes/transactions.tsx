import { createFileRoute } from "@tanstack/react-router";
import { AppShell, Card, SignInGate } from "@/components/AppShell";
import { TxRow } from "@/components/TxRow";
import { useTransactions } from "@/lib/data";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export const Route = createFileRoute("/transactions")({
  head: () => ({
    meta: [
      { title: "Transaction history — ParkSpot Wallet" },
      { name: "description", content: "All your wallet top-ups, charges and refunds." },
      { property: "og:title", content: "Transaction history — ParkSpot Wallet" },
      { property: "og:description", content: "Your ParkSpot Wallet history." },
    ],
  }),
  component: Tx,
});

function Tx() {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  const { data = [] } = useTransactions(user?.id);
  if (loading)
    return (
      <AppShell back title={t("history")}>
        <div />
      </AppShell>
    );
  if (!user)
    return (
      <AppShell back title={t("history")}>
        <SignInGate />
      </AppShell>
    );
  return (
    <AppShell back title={t("history")}>
      <div className="p-5">
        <Card>
          {data.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">{t("noTx")}</p>
          ) : (
            <div className="divide-y">
              {data.map((x) => (
                <TxRow key={x.id} tx={x} />
              ))}
            </div>
          )}
        </Card>
      </div>
    </AppShell>
  );
}
