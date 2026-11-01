import { Link } from "@tanstack/react-router";
import { Star, MapPin, Navigation } from "lucide-react";
import { imageFor, mad } from "@/lib/data";
import { formatDistance } from "@/lib/geo";
import { useI18n } from "@/lib/i18n";
import type { Database } from "@/integrations/supabase/types";

export type Facility = Database["public"]["Tables"]["facilities"]["Row"];

export function FacilityCard({
  f,
  compact,
  distanceM,
}: {
  f: Facility;
  compact?: boolean;
  distanceM?: number;
}) {
  const { t, lang } = useI18n();
  return (
    <Link
      to="/facility/$id"
      params={{ id: f.id }}
      className="block overflow-hidden rounded-3xl border bg-card shadow-soft transition-transform active:scale-[0.99]"
    >
      <div className={`relative ${compact ? "h-28" : "h-40"}`}>
        <img
          src={imageFor(f.image_key)}
          alt={f.name}
          loading="lazy"
          className="h-full w-full object-cover"
        />
        <span
          className={`absolute top-3 rounded-full px-2.5 py-1 text-xs font-semibold ltr:left-3 rtl:right-3 ${f.available > 0 ? "bg-card text-primary" : "bg-destructive text-destructive-foreground"}`}
        >
          {f.available > 0 ? `${f.available} ${t("spots")}` : t("full")}
        </span>
      </div>
      <div className="p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 className="font-semibold leading-tight">{lang === "ar" ? f.name_ar : f.name}</h3>
          <span className="flex items-center gap-1 text-sm font-medium">
            <Star className="h-4 w-4 fill-warning text-warning" />
            {f.rating}
          </span>
        </div>
        <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
          <MapPin className="h-3.5 w-3.5" />
          {f.address}, {f.city}
        </p>
        {distanceM !== undefined && (
          <p className="mt-1 flex items-center gap-1 text-xs font-medium text-primary">
            <Navigation className="h-3.5 w-3.5" />
            {t("away", { x: formatDistance(distanceM, lang) })}
          </p>
        )}
        <p className="mt-3 text-sm">
          <span className="text-lg font-bold text-primary">
            {mad(f.price_per_hour_cents, lang)}
          </span>{" "}
          <span className="text-muted-foreground">{t("perHour")}</span>
        </p>
      </div>
    </Link>
  );
}
