import { createFileRoute, Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { AppShell, Card, SignInGate } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { mad } from "@/lib/data";

export const Route = createFileRoute("/booking/$id")({
  head: () => ({ meta: [{ title: "Booking confirmed — ParkSpot AI" }, { name: "description", content: "Your parking booking and access code." }, { property: "og:title", content: "Booking confirmed — ParkSpot AI" }, { property: "og:description", content: "Your ParkSpot reservation." }] }),
  component: Confirm,
});

function Confirm() {
  const { id } = Route.useParams();
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const { data: b } = useQuery({
    queryKey: ["booking", id], enabled: !!user,
    queryFn: async () => (await supabase.from("bookings").select("*, facilities(name,name_ar,address,city)").eq("id", id).single()).data,
  });
  if (!user) return <AppShell><SignInGate /></AppShell>;
  return (
    <AppShell title={t("confirmed")}>
      <div className="p-5 text-center">
        <CheckCircle2 className="mx-auto mt-4 h-16 w-16 text-primary-glow animate-in zoom-in duration-500" />
        <h1 className="mt-3 font-display text-2xl font-semibold">{t("confirmed")}</h1>
        {b && (
          <Card className="mt-6 text-start">
            <p className="font-semibold">{lang === "ar" ? b.facilities?.name_ar : b.facilities?.name}</p>
            <p className="text-xs text-muted-foreground">{b.facilities?.address}, {b.facilities?.city}</p>
            <p className="mt-3 text-sm">{new Date(b.start_at).toLocaleString(lang)} · {b.hours}h</p>
            <p className="text-sm font-bold text-primary">{mad(b.total_cents, lang)}</p>
            <div className="mt-4 rounded-2xl bg-secondary p-4 text-center">
              <p className="text-xs text-muted-foreground">{t("accessCode")}</p>
              <p className="font-mono text-3xl font-bold tracking-[0.3em] text-primary">{b.access_code}</p>
            </div>
          </Card>
        )}
        <Link to="/bookings" className="mt-6 flex h-12 items-center justify-center rounded-full bg-primary font-semibold text-primary-foreground">{t("viewBookings")}</Link>
      </div>
    </AppShell>
  );
}
