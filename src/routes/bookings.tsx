import { createFileRoute } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AppShell, Card, SignInGate } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { mad } from "@/lib/data";

export const Route = createFileRoute("/bookings")({
  head: () => ({
    meta: [
      { title: "My bookings — ParkSpot AI" },
      { name: "description", content: "Your parking reservations and access codes." },
      { property: "og:title", content: "My bookings — ParkSpot AI" },
      { property: "og:description", content: "Manage your parking bookings." },
    ],
  }),
  component: Bookings,
});

function Bookings() {
  const { user, loading } = useAuth();
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const { data = [] } = useQuery({
    queryKey: ["bookings", user?.id],
    enabled: !!user,
    queryFn: async () =>
      (
        await supabase
          .from("bookings")
          .select("*, facilities(name,name_ar,city)")
          .eq("user_id", user!.id)
          .order("start_at", { ascending: false })
      ).data ?? [],
  });
  if (loading)
    return (
      <AppShell title={t("bookings")}>
        <div />
      </AppShell>
    );
  if (!user)
    return (
      <AppShell title={t("bookings")}>
        <SignInGate />
      </AppShell>
    );

  const cancel = async (id: string) => {
    if (!confirm(t("refundPolicy"))) return undefined;
    const { data: b, error } = await supabase.rpc("cancel_booking", { p_booking_id: id });
    if (error) {
      toast.error(error.message);
      return;
    }
    toast.success(`${t("refund")}: ${mad(b.refunded_cents, lang)}`);
    qc.invalidateQueries();
  };

  return (
    <AppShell title={t("bookings")}>
      <div className="space-y-3 p-5">
        {data.length === 0 && (
          <p className="py-10 text-center text-muted-foreground">{t("noBookings")}</p>
        )}
        {data.map((b) => (
          <Card key={b.id}>
            <div className="flex justify-between gap-2">
              <div>
                <p className="font-semibold">
                  {lang === "ar" ? b.facilities?.name_ar : b.facilities?.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {new Date(b.start_at).toLocaleString(lang)} · {b.hours}h
                </p>
              </div>
              <span
                className={`h-fit rounded-full px-2.5 py-1 text-xs font-semibold ${b.status === "confirmed" ? "bg-secondary text-primary" : "bg-muted text-muted-foreground"}`}
              >
                {b.status === "confirmed" ? t("active") : t("cancelled")}
              </span>
            </div>
            <div className="mt-3 flex items-center justify-between">
              <div>
                <p className="font-bold text-primary">{mad(b.total_cents, lang)}</p>
                {b.refunded_cents > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {t("refund")}: {mad(b.refunded_cents, lang)}
                  </p>
                )}
              </div>
              {b.status === "confirmed" && (
                <span className="font-mono text-sm font-bold tracking-widest">{b.access_code}</span>
              )}
            </div>
            {b.status === "confirmed" && (
              <button
                onClick={() => cancel(b.id)}
                className="mt-3 h-10 w-full rounded-full border text-sm font-semibold text-destructive"
              >
                {t("cancel")}
              </button>
            )}
          </Card>
        ))}
      </div>
    </AppShell>
  );
}
