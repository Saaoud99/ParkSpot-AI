import { createFileRoute, ClientOnly } from "@tanstack/react-router";
import { lazy, Suspense, useCallback, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { FacilityCard } from "@/components/FacilityCard";
import { useFacilities } from "@/lib/data";
import { useI18n } from "@/lib/i18n";

const ParkingMap = lazy(() => import("@/components/ParkingMap"));

export const Route = createFileRoute("/map")({
  head: () => ({ meta: [{ title: "Parking map — ParkSpot AI" }, { name: "description", content: "See parking facilities and prices on a live map." }, { property: "og:title", content: "Parking map — ParkSpot AI" }, { property: "og:description", content: "Map-based parking discovery." }] }),
  component: MapPage,
});

function MapPage() {
  const { t } = useI18n();
  const { data = [] } = useFacilities();
  const [sel, setSel] = useState<string | null>(null);
  const onSelect = useCallback((id: string) => setSel(id), []);
  const chosen = data.find((f) => f.id === sel);
  return (
    <AppShell title={t("map")}>
      {/* Fill the shell's scroll area exactly — no page scroll on this
          screen, the map itself handles pan/zoom. */}
      <div className="relative h-full min-h-0 w-full overflow-hidden">
        <ClientOnly fallback={<div className="h-full animate-pulse bg-secondary" />}>
          <Suspense fallback={<div className="h-full animate-pulse bg-secondary" />}>
            {data.length > 0 && <ParkingMap facilities={data} onSelect={onSelect} />}
          </Suspense>
        </ClientOnly>
        <div className="absolute inset-x-4 bottom-4 z-[500]">
          {chosen ? <FacilityCard f={chosen} compact /> : (
            <div className="no-scrollbar flex gap-3 overflow-x-auto">
              {data.map((f) => <div key={f.id} className="w-64 shrink-0"><FacilityCard f={f} compact /></div>)}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
