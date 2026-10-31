import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Activity, Bell, BookOpen, Bot, Building2, Camera, ChartBar, FileText, LayoutDashboard,
  LogOut, RefreshCw, Settings as SettingsIcon, Users, Wallet as WalletIcon,
} from "lucide-react";
import { SignInGate } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { mad } from "@/lib/data";
import { adminApi, downloadCsv } from "@/lib/admin";
import { metaBackendConfigured } from "@/lib/meta";
import logo from "@/assets/logo.png";

export const Route = createFileRoute("/admin")({
  head: () => ({ meta: [{ title: "Super Admin — ParkSpot AI" }, { name: "description", content: "ParkSpot AI administration control center." }] }),
  component: AdminPage,
});

const SECTIONS = [
  { id: "overview", icon: LayoutDashboard, key: "aOverview" },
  { id: "users", icon: Users, key: "aUsers" },
  { id: "facilities", icon: Building2, key: "aFacilities" },
  { id: "bookings", icon: BookOpen, key: "aBookings" },
  { id: "pricing", icon: ChartBar, key: "aPricing" },
  { id: "ai", icon: Bot, key: "aAI" },
  { id: "cameras", icon: Camera, key: "aCameras" },
  { id: "payments", icon: WalletIcon, key: "aPayments" },
  { id: "reports", icon: FileText, key: "aReports" },
  { id: "incidents", icon: Bell, key: "aIncidents" },
  { id: "audit", icon: Activity, key: "aAudit" },
  { id: "settings", icon: SettingsIcon, key: "aSettings" },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];
type ConfirmState = { title: string; run: (reason: string) => Promise<unknown> } | null;

const inputCls = "h-10 w-full rounded-xl border bg-background px-3 text-sm outline-none focus:border-primary";
const btnCls = "h-9 rounded-full bg-primary px-3 text-xs font-semibold text-primary-foreground disabled:opacity-50";
const ghostCls = "h-9 rounded-full border px-3 text-xs font-medium disabled:opacity-50";

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-3xl border bg-card p-4 shadow-soft ${className}`}>{children}</div>;
}

function Stat({ label, value }: { label: string; value: ReactNode }) {
  return <Card><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-bold">{value}</p></Card>;
}

function ConfirmModal({ state, close }: { state: ConfirmState; close: () => void }) {
  const { t } = useI18n();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  if (!state) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-3xl bg-card p-5 shadow-lift">
        <h3 className="font-display text-lg font-semibold">{state.title}</h3>
        <label className="mt-4 block text-xs font-medium text-muted-foreground">{t("reasonLbl")}</label>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} className="mt-1 w-full rounded-xl border bg-background p-3 text-sm outline-none focus:border-primary" />
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={close} className={ghostCls}>{t("cancel")}</button>
          <button disabled={reason.trim().length < 3 || busy} className={btnCls}
            onClick={async () => {
              setBusy(true);
              try { await state.run(reason.trim()); toast.success(t("saved")); close(); }
              catch (e) { toast.error((e as Error).message); }
              finally { setBusy(false); }
            }}>{t("confirmAction")}</button>
        </div>
      </div>
    </div>
  );
}

function useSection<T>(key: string, fn: () => Promise<T>, enabled = true) {
  return useQuery({ queryKey: ["admin", key], queryFn: fn, enabled: enabled && metaBackendConfigured(), retry: false });
}

function Overview({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t, lang } = useI18n();
  const { data, isLoading, refetch } = useSection("overview", adminApi.overview);
  if (!metaBackendConfigured()) return <Card>{t("backendOff")}</Card>;
  if (isLoading || !data) return <Card>{t("transcribing")}</Card>;
  const pie = Object.entries(data.bookings_by_status ?? {}).map(([k, v]) => ({ name: k, value: v as number }));
  const COLORS = ["#059669", "#f59e0b", "#ef4444", "#64748b"];
  return (
    <div className="space-y-4">
      <div className="flex justify-end"><button className={ghostCls} onClick={() => void refetch()}><RefreshCw className="me-1 inline h-3.5 w-3.5" />{t("refreshLbl")}</button></div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={t("totalDrivers")} value={data.users_total} />
        <Stat label={t("suspendedUsers")} value={data.users_suspended} />
        <Stat label={t("totalFacilitiesLbl")} value={`${data.facilities_active}/${data.facilities_total}`} />
        <Stat label={t("authorizedSpaces")} value={data.spaces_authorized} />
        <Stat label={t("availableSpaces")} value={data.spaces_available} />
        <Stat label={t("activeBookings")} value={data.bookings_by_status?.confirmed ?? 0} />
        <Stat label={t("camerasLbl")} value={`${data.cameras_active}/${data.cameras_total}`} />
        <Stat label={t("revenueDemo")} value={mad(data.revenue_cents, lang)} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <p className="mb-2 font-semibold">{t("bookingsPerDay")}</p>
          <div className="h-56" dir="ltr">
            <ResponsiveContainer><BarChart data={data.bookings_per_day}>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
              <Tooltip /><Bar dataKey="count" fill="#059669" radius={[4, 4, 0, 0]} />
            </BarChart></ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <p className="mb-2 font-semibold">{t("statusDistribution")}</p>
          <div className="h-56" dir="ltr">
            <ResponsiveContainer><PieChart>
              <Pie data={pie} dataKey="value" nameKey="name" outerRadius={80} label>
                {pie.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie><Tooltip />
            </PieChart></ResponsiveContainer>
          </div>
        </Card>
      </div>
      <Card>
        <p className="mb-2 font-semibold">{t("recentActivity")}</p>
        {(data.recent_audit ?? []).length === 0 && <p className="text-sm text-muted-foreground">{t("noData")}</p>}
        <ul className="space-y-1 text-sm">
          {(data.recent_audit ?? []).map((a: { id: string; action: string; target_type: string; created_at: string }) => (
            <li key={a.id} className="flex justify-between border-b py-1.5 last:border-0">
              <span><b>{a.action}</b> · {a.target_type}</span>
              <span className="text-xs text-muted-foreground">{new Date(a.created_at).toLocaleString()}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function UsersSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const { data, isLoading } = useSection(`users-${search}`, () => adminApi.users(`limit=100&search=${encodeURIComponent(search)}`));
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });
  const roleName = (r: string) => (r === "admin" ? t("roleAdmin") : r === "partner" ? t("rolePartner") : t("roleUser"));
  return (
    <div className="space-y-3">
      <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={`${t("searchLbl")}…`} className={inputCls} />
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead><tr className="border-b text-start text-xs text-muted-foreground">
            <th className="p-3 text-start">{t("name")}</th><th className="p-3 text-start">{t("plate")}</th>
            <th className="p-3 text-start">Roles</th><th className="p-3 text-start">{t("incidentStatus")}</th><th className="p-3 text-start">{t("actionsLbl")}</th>
          </tr></thead>
          <tbody>
            {isLoading && <tr><td className="p-3" colSpan={5}>…</td></tr>}
            {(data?.users ?? []).map((u: { id: string; display_name?: string; vehicle_plate?: string; status: string; roles: string[] }) => (
              <tr key={u.id} className="border-b last:border-0">
                <td className="p-3"><b>{u.display_name ?? "—"}</b><br /><span className="text-xs text-muted-foreground">{u.id.slice(0, 8)}…</span></td>
                <td className="p-3">{u.vehicle_plate ?? "—"}</td>
                <td className="p-3">{u.roles.map(roleName).join(", ") || "—"}</td>
                <td className="p-3">{u.status}</td>
                <td className="p-3">
                  <div className="flex flex-wrap gap-1">
                    {u.status === "active"
                      ? <button className={ghostCls} onClick={() => confirm({ title: `${t("suspend")} — ${u.display_name ?? u.id.slice(0, 8)}`, run: async (r) => { await adminApi.suspendUser(u.id, r); invalidate(); } })}>{t("suspend")}</button>
                      : <button className={ghostCls} onClick={() => confirm({ title: `${t("reactivate")} — ${u.display_name ?? u.id.slice(0, 8)}`, run: async (r) => { await adminApi.reactivateUser(u.id, r); invalidate(); } })}>{t("reactivate")}</button>}
                    {(["admin", "partner"] as const).map((role) => (
                      u.roles.includes(role)
                        ? <button key={role} className={ghostCls} onClick={() => confirm({ title: `${t("revokeRole")} ${roleName(role)}`, run: async (r) => { await adminApi.setRole(u.id, role, "revoke", r); invalidate(); } })}>{t("revokeRole")} {roleName(role)}</button>
                        : <button key={role} className={ghostCls} onClick={() => confirm({ title: `${t("grantRole")} ${roleName(role)}`, run: async (r) => { await adminApi.setRole(u.id, role, "grant", r); invalidate(); } })}>{t("grantRole")} {roleName(role)}</button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.users.length === 0 && <p className="p-4 text-sm text-muted-foreground">{t("noData")}</p>}
      </Card>
    </div>
  );
}

function FacilitiesSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("facilities", adminApi.facilities);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });
  const [form, setForm] = useState({ name: "", name_ar: "", city: "Casablanca", address: "", lat: 33.59, lng: -7.62, price: 1500, total: 100, authorized: 50, available: 50 });
  const upd = (k: string, v: string | number) => setForm((f) => ({ ...f, [k]: v }));
  return (
    <div className="space-y-3">
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead><tr className="border-b text-xs text-muted-foreground">
            <th className="p-3 text-start">{t("name")}</th><th className="p-3 text-start">{t("totalCapacityLbl")}</th>
            <th className="p-3 text-start">{t("authorizedCapacityLbl")}</th><th className="p-3 text-start">{t("availableSpaces")}</th>
            <th className="p-3 text-start">{t("incidentStatus")}</th><th className="p-3 text-start">{t("actionsLbl")}</th>
          </tr></thead>
          <tbody>
            {(data?.facilities ?? []).map((f: { id: string; name: string; total_capacity: number; authorized_capacity: number; available: number; active: boolean }) => (
              <tr key={f.id} className="border-b last:border-0">
                <td className="p-3 font-medium">{f.name}</td><td className="p-3">{f.total_capacity}</td>
                <td className="p-3">{f.authorized_capacity}</td><td className="p-3">{f.available}</td>
                <td className="p-3">{f.active ? t("enabledLbl") : t("disabledLbl")}</td>
                <td className="p-3">
                  <button className={ghostCls} onClick={() => confirm({
                    title: `${f.active ? t("disabledLbl") : t("enabledLbl")} — ${f.name}`,
                    run: async (r) => { await adminApi.updateFacility(f.id, { active: !f.active, reason: r }); invalidate(); },
                  })}>{f.active ? t("disabledLbl") : t("enabledLbl")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card>
        <p className="mb-3 font-semibold">{t("newFacility")}</p>
        <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
          <input placeholder={t("name")} value={form.name} onChange={(e) => upd("name", e.target.value)} className={inputCls} />
          <input placeholder="الاسم" value={form.name_ar} onChange={(e) => upd("name_ar", e.target.value)} className={inputCls} />
          <input placeholder="City" value={form.city} onChange={(e) => upd("city", e.target.value)} className={inputCls} />
          <input placeholder="Address" value={form.address} onChange={(e) => upd("address", e.target.value)} className={inputCls} />
          <input type="number" step="0.0001" placeholder="Lat" value={form.lat} onChange={(e) => upd("lat", Number(e.target.value))} className={inputCls} />
          <input type="number" step="0.0001" placeholder="Lng" value={form.lng} onChange={(e) => upd("lng", Number(e.target.value))} className={inputCls} />
          <input type="number" placeholder={t("priceCents")} value={form.price} onChange={(e) => upd("price", Number(e.target.value))} className={inputCls} />
          <input type="number" placeholder={t("totalCapacityLbl")} value={form.total} onChange={(e) => upd("total", Number(e.target.value))} className={inputCls} />
          <input type="number" placeholder={t("authorizedCapacityLbl")} value={form.authorized} onChange={(e) => upd("authorized", Number(e.target.value))} className={inputCls} />
          <input type="number" placeholder={t("availableSpaces")} value={form.available} onChange={(e) => upd("available", Number(e.target.value))} className={inputCls} />
        </div>
        <button className={`${btnCls} mt-3`} onClick={async () => {
          try {
            await adminApi.createFacility({ name: form.name, name_ar: form.name_ar, city: form.city, address: form.address, lat: form.lat, lng: form.lng, price_per_hour_cents: form.price, total_capacity: form.total, authorized_capacity: form.authorized, available: form.available, features: [], open_24h: true, active: true });
            toast.success(t("saved")); invalidate();
          } catch (e) { toast.error((e as Error).message); }
        }}>{t("createLbl")}</button>
      </Card>
    </div>
  );
}

function BookingsSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const { data } = useSection(`bookings-${status}`, () => adminApi.bookings(`limit=100${status ? `&status=${status}` : ""}`));
  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        {["", "confirmed", "cancelled", "completed"].map((s) => (
          <button key={s} onClick={() => setStatus(s)} className={status === s ? btnCls : ghostCls}>{s || "All"}</button>
        ))}
      </div>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead><tr className="border-b text-xs text-muted-foreground">
            <th className="p-3 text-start">ID</th><th className="p-3 text-start">{t("name")}</th>
            <th className="p-3 text-start">{t("total")}</th><th className="p-3 text-start">{t("incidentStatus")}</th><th className="p-3 text-start">{t("actionsLbl")}</th>
          </tr></thead>
          <tbody>
            {(data?.bookings ?? []).map((b: { id: string; facility_name?: string; total_cents: number; status: string; start_at: string }) => (
              <tr key={b.id} className="border-b last:border-0">
                <td className="p-3 text-xs">{b.id.slice(0, 8)}…<br />{new Date(b.start_at).toLocaleString()}</td>
                <td className="p-3">{b.facility_name ?? "—"}</td>
                <td className="p-3">{mad(b.total_cents, lang)}</td>
                <td className="p-3">{b.status}</td>
                <td className="p-3">{b.status === "confirmed" && (
                  <button className={ghostCls} onClick={() => confirm({ title: `${t("cancel")} — ${b.id.slice(0, 8)}`, run: async (r) => { await adminApi.cancelBooking(b.id, r); qc.invalidateQueries({ queryKey: ["admin"] }); } })}>{t("cancel")}</button>
                )}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.bookings.length === 0 && <p className="p-4 text-sm text-muted-foreground">{t("noData")}</p>}
      </Card>
    </div>
  );
}

function PricingSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("pricing", adminApi.pricing);
  const [prices, setPrices] = useState<Record<string, string>>({});
  return (
    <div className="space-y-3">
      <Card><p className="text-sm text-muted-foreground">
        {t("priceCents")} · bounds {data?.pricing_min_cents}–{data?.pricing_max_cents} · engine: {data?.engine}
      </p></Card>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-sm">
          <thead><tr className="border-b text-xs text-muted-foreground">
            <th className="p-3 text-start">{t("name")}</th><th className="p-3 text-start">{t("total")}</th><th className="p-3 text-start">{t("save")}</th>
          </tr></thead>
          <tbody>
            {(data?.facilities ?? []).map((f: { id: string; name: string; price_per_hour_cents: number }) => (
              <tr key={f.id} className="border-b last:border-0">
                <td className="p-3 font-medium">{f.name}</td>
                <td className="p-3">
                  <input type="number" className="h-9 w-32 rounded-xl border bg-background px-2"
                    value={prices[f.id] ?? String(f.price_per_hour_cents)}
                    onChange={(e) => setPrices((p) => ({ ...p, [f.id]: e.target.value }))} />
                  <span className="ms-2 text-xs text-muted-foreground">= {mad(Number(prices[f.id] ?? f.price_per_hour_cents), lang)}{t("perHour")}</span>
                </td>
                <td className="p-3">
                  <button className={ghostCls} onClick={() => confirm({ title: `${t("aPricing")} — ${f.name}`, run: async (r) => { await adminApi.setPrice(f.id, Number(prices[f.id]), r); qc.invalidateQueries({ queryKey: ["admin"] }); } })}>{t("save")}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card>
        <p className="mb-2 font-semibold">{t("history")}</p>
        {(data?.history ?? []).length === 0 && <p className="text-sm text-muted-foreground">{t("noData")}</p>}
        <ul className="space-y-1 text-sm">{(data?.history ?? []).map((h: { id: string; created_at: string; metadata?: { price_per_hour_cents?: number } }) => (
          <li key={h.id} className="flex justify-between border-b py-1.5 last:border-0">
            <span>{h.metadata?.price_per_hour_cents} cents</span>
            <span className="text-xs text-muted-foreground">{new Date(h.created_at).toLocaleString()}</span>
          </li>))}
        </ul>
      </Card>
    </div>
  );
}

function AiSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("ai", adminApi.aiStatus);
  const health = useMutation({ mutationFn: (s: string) => adminApi.aiHealth(s) });
  const services = data?.services ?? {};
  const metrics = data?.metrics?.services ?? {};
  const rows: { id: string; label: string; feature: string }[] = [
    { id: "muse_spark", label: "Muse Spark", feature: "assistant" },
    { id: "muse_voice", label: "Muse Voice Transcribe", feature: "voice" },
    { id: "sam", label: "SAM 3.1", feature: "vision" },
    { id: "easyocr", label: "EasyOCR", feature: "vision" },
  ];
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      {rows.map((row) => {
        const s = services[row.id] ?? {};
        const m = metrics[row.id] ?? {};
        const res = health.data && (health.variables === row.id) ? health.data : null;
        return (
          <Card key={row.id}>
            <div className="flex items-center justify-between">
              <p className="font-semibold">{row.label}</p>
              <button className={ghostCls} disabled={health.isPending} onClick={() => health.mutate(row.id)}>{t("healthCheck")}</button>
            </div>
            <dl className="mt-2 space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-muted-foreground">{t("configuredLbl")}</dt><dd>{s.configured ? "✓" : "—"}{s.model ? ` · ${s.model}` : ""}</dd></div>
              <div className="flex justify-between"><dt className="text-muted-foreground">{t("enabledLbl")}</dt><dd>{s.enabled ? t("enabledLbl") : t("disabledLbl")}</dd></div>
              <div className="flex justify-between"><dt className="text-muted-foreground">Requests ({t("sinceRestart")})</dt><dd>{m.requests ?? 0} · err {m.errors ?? 0}{m.avg_latency_ms ? ` · ${m.avg_latency_ms} ms` : ""}</dd></div>
              {m.last_error && <div className="flex justify-between gap-2"><dt className="text-muted-foreground">Last error</dt><dd className="truncate text-destructive">{m.last_error}</dd></div>}
              {res && <div className="flex justify-between gap-2"><dt className="text-muted-foreground">{t("healthCheck")}</dt><dd>{res.reachable ? t("reachableLbl") : "—"} · {res.tested_ok ? t("testedOk") : res.detail}</dd></div>}
            </dl>
            <button className={`${ghostCls} mt-3`} onClick={() => confirm({
              title: `${row.label}: ${s.enabled ? t("disabledLbl") : t("enabledLbl")}`,
              run: async (r) => { await adminApi.aiToggle(row.feature, !s.enabled, r); qc.invalidateQueries({ queryKey: ["admin"] }); },
            })}>{s.enabled ? t("disabledLbl") : t("enabledLbl")}</button>
          </Card>
        );
      })}
    </div>
  );
}

function CamerasSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("cameras", adminApi.cameras);
  const [label, setLabel] = useState("");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });
  return (
    <div className="space-y-3">
      <Card>
        <div className="flex gap-2">
          <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Camera label" className={inputCls} />
          <button className={btnCls} onClick={async () => {
            try { await adminApi.createCamera({ label, status: "active" }); setLabel(""); invalidate(); }
            catch (e) { toast.error((e as Error).message); }
          }}>{t("createLbl")}</button>
        </div>
      </Card>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[560px] text-sm">
          <thead><tr className="border-b text-xs text-muted-foreground">
            <th className="p-3 text-start">Camera</th><th className="p-3 text-start">{t("incidentStatus")}</th><th className="p-3 text-start">{t("actionsLbl")}</th>
          </tr></thead>
          <tbody>
            {(data?.cameras ?? []).map((cam: { id: string; label: string; status: string }) => (
              <tr key={cam.id} className="border-b last:border-0">
                <td className="p-3 font-medium">{cam.label}</td><td className="p-3">{cam.status}</td>
                <td className="p-3"><button className={ghostCls} onClick={() => confirm({
                  title: `${cam.label}: ${cam.status === "active" ? t("disabledLbl") : t("enabledLbl")}`,
                  run: async (r) => { await adminApi.updateCamera(cam.id, { status: cam.status === "active" ? "inactive" : "active", reason: r }); invalidate(); },
                })}>{cam.status === "active" ? t("disabledLbl") : t("enabledLbl")}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card>
        <p className="mb-2 font-semibold">{t("recent")}</p>
        {(data?.events ?? []).length === 0 && <p className="text-sm text-muted-foreground">{t("noData")}</p>}
        <ul className="space-y-1 text-sm">{(data?.events ?? []).map((e: { id: string; kind: string; access_result?: string; ocr_confidence?: number; simulated: boolean; created_at: string }) => (
          <li key={e.id} className="flex justify-between border-b py-1.5 last:border-0">
            <span>{e.kind} · {e.access_result ?? "—"}{e.simulated ? " · SIM" : ""}{e.ocr_confidence ? ` · OCR ${Math.round(Number(e.ocr_confidence) * 100)}%` : ""}</span>
            <span className="text-xs text-muted-foreground">{new Date(e.created_at).toLocaleString()}</span>
          </li>))}
        </ul>
      </Card>
    </div>
  );
}

function PaymentsSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("wallets", adminApi.wallets);
  const [selected, setSelected] = useState<string | null>(null);
  const { data: txData } = useSection(`tx-${selected}`, () => adminApi.walletTx(selected!), !!selected);
  const [amount, setAmount] = useState("");
  return (
    <div className="space-y-3">
      <Card className="border-warning/50 bg-warning/10"><p className="text-sm font-medium">{t("demoBanner")}</p></Card>
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-sm">
          <thead><tr className="border-b text-xs text-muted-foreground">
            <th className="p-3 text-start">{t("name")}</th><th className="p-3 text-start">{t("available")}</th><th className="p-3 text-start">{t("actionsLbl")}</th>
          </tr></thead>
          <tbody>
            {(data?.wallets ?? []).map((w: { user_id: string; display_name?: string; available_cents: number }) => (
              <tr key={w.user_id} className="border-b last:border-0">
                <td className="p-3">{w.display_name ?? w.user_id.slice(0, 8)}</td>
                <td className="p-3 font-semibold">{mad(w.available_cents, lang)}</td>
                <td className="p-3"><button className={ghostCls} onClick={() => setSelected(w.user_id)}>{t("history")}</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {selected && (
        <Card>
          <p className="font-semibold">{t("history")} — {selected.slice(0, 8)}…</p>
          <div className="mt-2 flex gap-2">
            <input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={t("amountCents")} className={inputCls} />
            <button className={btnCls} onClick={() => confirm({
              title: t("adjustBalance"),
              run: async (r) => { await adminApi.adjustWallet(selected, Number(amount), r); qc.invalidateQueries({ queryKey: ["admin"] }); },
            })}>{t("adjustBalance")}</button>
          </div>
          <ul className="mt-3 space-y-1 text-sm">
            {(txData?.transactions ?? []).map((tx: { id: string; type: string; amount_cents: number; status: string; created_at: string }) => (
              <li key={tx.id} className="flex justify-between border-b py-1.5 last:border-0">
                <span>{tx.type} · {tx.status}</span><span>{mad(tx.amount_cents, lang)} · {new Date(tx.created_at).toLocaleDateString()}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function ReportsSection() {
  const { t, lang } = useI18n();
  const [days, setDays] = useState(30);
  const { data } = useSection(`reports-${days}`, () => adminApi.reports(days));
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {[7, 30, 90].map((d) => <button key={d} onClick={() => setDays(d)} className={days === d ? btnCls : ghostCls}>{d}d</button>)}
        <button className={ghostCls} onClick={() => void downloadCsv().catch((e) => toast.error((e as Error).message))}>{t("exportCsv")}</button>
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3">
        <Stat label={t("aBookings")} value={data?.total ?? 0} />
        <Stat label={t("cancelled")} value={data?.cancelled ?? 0} />
        <Stat label="Cancellation %" value={`${Math.round((data?.cancellation_rate ?? 0) * 100)}%`} />
      </div>
      <Card>
        <p className="mb-2 font-semibold">{t("bookingsPerDay")}</p>
        <div className="h-56" dir="ltr">
          <ResponsiveContainer><BarChart data={data?.bookings_per_day ?? []}>
            <XAxis dataKey="date" tick={{ fontSize: 10 }} /><YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
            <Tooltip /><Bar dataKey="count" fill="#059669" radius={[4, 4, 0, 0]} />
          </BarChart></ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <p className="mb-2 font-semibold">{t("nearby")}</p>
        <ul className="space-y-1 text-sm">
          {(data?.facility_performance ?? []).map((f: { facility_id: string; name?: string; bookings: number; revenue_cents: number }) => (
            <li key={f.facility_id} className="flex justify-between border-b py-1.5 last:border-0">
              <span>{f.name ?? f.facility_id.slice(0, 8)}</span><span>{f.bookings} · {mad(f.revenue_cents, lang)}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function IncidentsSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("incidents", () => adminApi.incidents());
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });
  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full min-w-[640px] text-sm">
        <thead><tr className="border-b text-xs text-muted-foreground">
          <th className="p-3 text-start">{t("name")}</th><th className="p-3 text-start">{t("incidentStatus")}</th><th className="p-3 text-start">{t("actionsLbl")}</th>
        </tr></thead>
        <tbody>
          {(data?.incidents ?? []).map((i: { id: string; kind: string; title: string; status: string; created_at: string }) => (
            <tr key={i.id} className="border-b last:border-0">
              <td className="p-3"><b>{i.title}</b><br /><span className="text-xs text-muted-foreground">{i.kind} · {new Date(i.created_at).toLocaleString()}</span></td>
              <td className="p-3">{i.status}</td>
              <td className="p-3">
                <div className="flex gap-1">
                  {(["investigating", "resolved", "dismissed"] as const).map((s) => (
                    <button key={s} className={ghostCls} onClick={() => confirm({ title: `${i.title} → ${s}`, run: async (r) => { await adminApi.updateIncident(i.id, s, r); invalidate(); } })}>{s}</button>
                  ))}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {data && data.incidents.length === 0 && <p className="p-4 text-sm text-muted-foreground">{t("noData")}</p>}
    </Card>
  );
}

function AuditSection() {
  const { t } = useI18n();
  const [action, setAction] = useState("");
  const { data } = useSection(`audit-${action}`, () => adminApi.audit(`limit=100${action ? `&action=${encodeURIComponent(action)}` : ""}`));
  return (
    <div className="space-y-3">
      <input value={action} onChange={(e) => setAction(e.target.value)} placeholder="action e.g. wallet.adjust" className={inputCls} />
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[720px] text-sm">
          <thead><tr className="border-b text-xs text-muted-foreground">
            <th className="p-3 text-start">Action</th><th className="p-3 text-start">Target</th>
            <th className="p-3 text-start">{t("reasonLbl")}</th><th className="p-3 text-start">When</th>
          </tr></thead>
          <tbody>
            {(data?.entries ?? []).map((e: { id: string; action: string; target_type: string; target_id?: string; reason?: string; actor_id: string; created_at: string }) => (
              <tr key={e.id} className="border-b last:border-0">
                <td className="p-3 font-medium">{e.action}</td>
                <td className="p-3 text-xs">{e.target_type}:{(e.target_id ?? "").slice(0, 8)}<br />by {e.actor_id.slice(0, 8)}</td>
                <td className="p-3">{e.reason ?? "—"}</td>
                <td className="p-3 text-xs">{new Date(e.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.entries.length === 0 && <p className="p-4 text-sm text-muted-foreground">{t("noData")}</p>}
      </Card>
    </div>
  );
}

function SettingsSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("settings", adminApi.settings);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const current: Record<string, unknown> = data?.settings ?? {};
  const field = (key: string, label: string, type = "text") => (
    <label className="block">
      <span className="text-xs font-medium text-muted-foreground">{label}</span>
      <input type={type} className={inputCls} value={draft[key] ?? String(current[key] ?? "")}
        onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))} />
    </label>
  );
  return (
    <Card>
      <div className="grid gap-3 sm:grid-cols-2">
        {field("app_name", "App name")}
        {field("nearby_default_radius_km", "Nearby radius (km)", "number")}
        {field("hold_expiry_minutes", "Hold expiry (minutes)", "number")}
        {field("cancellation_window_hours", "Full-refund window (hours)", "number")}
        {field("pricing_min_cents", "Pricing min (cents)", "number")}
        {field("pricing_max_cents", "Pricing max (cents)", "number")}
      </div>
      <button className={`${btnCls} mt-4`} onClick={() => confirm({
        title: t("saveSettings"),
        run: async (r) => {
          const parsed: Record<string, unknown> = {};
          for (const [k, v] of Object.entries(draft)) parsed[k] = k === "app_name" ? v : Number(v);
          await adminApi.updateSettings(parsed, r);
          qc.invalidateQueries({ queryKey: ["admin"] });
        },
      })}>{t("saveSettings")}</button>
      <p className="mt-3 text-xs text-muted-foreground">{t("demoNote")}</p>
    </Card>
  );
}

function AdminPage() {
  const { t } = useI18n();
  const { user, roles, loading } = useAuth();
  const [section, setSection] = useState<SectionId>("overview");
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);
  const confirm = (s: ConfirmState) => setConfirmState(s);

  if (loading) return <div className="p-8 text-sm text-muted-foreground">…</div>;
  if (!user) return <div className="mx-auto max-w-md p-6"><SignInGate /></div>;
  if (!roles.includes("admin")) {
    return (
      <div className="mx-auto max-w-md p-6">
        <Card><p className="font-semibold">{t("adminRestricted")}</p>
          <Link to="/home" className="mt-3 inline-block text-sm font-medium text-primary">{t("home")}</Link></Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="mx-auto flex max-w-[1400px]">
        <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-e bg-card p-4 lg:block">
          <div className="flex items-center gap-2 px-2">
            <img src={logo} alt="ParkSpot AI" className="h-9 w-9 object-contain" />
            <div><p className="font-display font-semibold leading-tight">ParkSpot AI</p>
              <p className="text-xs text-muted-foreground">{t("adminTitle")}</p></div>
          </div>
          <nav className="mt-6 space-y-1">
            {SECTIONS.map((s) => (
              <button key={s.id} onClick={() => setSection(s.id)}
                className={`flex w-full items-center gap-2 rounded-full px-3 py-2 text-sm font-medium ${section === s.id ? "bg-primary text-primary-foreground" : "hover:bg-secondary"}`}>
                <s.icon className="h-4 w-4" />{t(s.key)}
              </button>
            ))}
          </nav>
          <div className="mt-8 border-t pt-4">
            <p className="truncate px-2 text-xs text-muted-foreground">{user.email}</p>
            <button onClick={() => void supabase.auth.signOut()} className="mt-2 flex w-full items-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-destructive hover:bg-destructive/10">
              <LogOut className="h-4 w-4" />{t("logout")}
            </button>
          </div>
        </aside>
        <main className="min-w-0 flex-1 p-4 sm:p-6">
          <div className="mb-4 flex items-center justify-between lg:hidden">
            <p className="font-display text-lg font-semibold">{t("adminTitle")}</p>
            <button onClick={() => void supabase.auth.signOut()} className="flex items-center gap-1 text-sm font-medium text-destructive">
              <LogOut className="h-4 w-4" />{t("logout")}
            </button>
          </div>
          <nav className="no-scrollbar mb-4 flex gap-2 overflow-x-auto pb-1 lg:hidden">
            {SECTIONS.map((s) => (
              <button key={s.id} onClick={() => setSection(s.id)}
                className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium ${section === s.id ? "border-primary bg-primary text-primary-foreground" : "bg-card"}`}>
                <s.icon className="h-3.5 w-3.5" />{t(s.key)}
              </button>
            ))}
          </nav>
          <h1 className="mb-4 font-display text-2xl font-semibold">{t(SECTIONS.find((s) => s.id === section)!.key)}</h1>
          {!metaBackendConfigured() && <Card className="mb-4">{t("backendOff")}</Card>}
          {section === "overview" && <Overview confirm={confirm} />}
          {section === "users" && <UsersSection confirm={confirm} />}
          {section === "facilities" && <FacilitiesSection confirm={confirm} />}
          {section === "bookings" && <BookingsSection confirm={confirm} />}
          {section === "pricing" && <PricingSection confirm={confirm} />}
          {section === "ai" && <AiSection confirm={confirm} />}
          {section === "cameras" && <CamerasSection confirm={confirm} />}
          {section === "payments" && <PaymentsSection confirm={confirm} />}
          {section === "reports" && <ReportsSection />}
          {section === "incidents" && <IncidentsSection confirm={confirm} />}
          {section === "audit" && <AuditSection />}
          {section === "settings" && <SettingsSection confirm={confirm} />}
        </main>
      </div>
      <ConfirmModal state={confirmState} close={() => setConfirmState(null)} />
    </div>
  );
}
