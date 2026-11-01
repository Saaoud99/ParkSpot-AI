import { ArrowDownLeft, ArrowUpRight, RotateCcw } from "lucide-react";
import { mad } from "@/lib/data";
import { useI18n } from "@/lib/i18n";
import type { Database } from "@/integrations/supabase/types";

type Tx = Database["public"]["Tables"]["wallet_transactions"]["Row"];

export function TxRow({ tx }: { tx: Tx }) {
  const { t, lang } = useI18n();
  const Icon =
    tx.type === "topup" ? ArrowDownLeft : tx.type === "refund" ? RotateCcw : ArrowUpRight;
  const statusCls =
    tx.status === "succeeded"
      ? "text-primary"
      : tx.status === "failed"
        ? "text-destructive"
        : "text-warning";
  return (
    <div className="flex items-center gap-3 py-3">
      <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-secondary">
        <Icon className="h-5 w-5 text-primary" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">
          {t(tx.type as "topup")}
          {tx.is_demo ? " · DEMO" : ""}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {tx.description} · {tx.reference}
        </p>
        <p className="text-xs text-muted-foreground">
          {new Date(tx.created_at).toLocaleString(lang)}
        </p>
      </div>
      <div className="text-end">
        <p className={`text-sm font-bold ${tx.amount_cents < 0 ? "" : "text-primary"}`}>
          {tx.amount_cents > 0 ? "+" : ""}
          {mad(tx.amount_cents, lang)}
        </p>
        <p className={`text-xs font-medium ${statusCls}`}>{t(tx.status as "succeeded")}</p>
      </div>
    </div>
  );
}
