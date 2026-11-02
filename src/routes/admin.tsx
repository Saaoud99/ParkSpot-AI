import { createFileRoute, Link } from "@tanstack/react-router";
import { useState, useMemo, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Activity, AlertCircle, AlertTriangle, ArrowDownRight, ArrowUpRight, BarChart3, Bell,
  BookOpen, Bot, Building2, Camera, CheckCircle2, ChevronDown, ChevronRight, Copy,
  Database, Download, ExternalLink, Eye, FileSpreadsheet, FileText, Filter, Globe, HelpCircle,
  Info, LayoutDashboard, LogOut, MoreHorizontal, Plus, RefreshCw, Search,
  Settings as SettingsIcon, Shield, ShieldAlert, ShieldCheck, Sliders, Sparkles,
  Trash2, UserCheck, UserPlus, Users, UserX, Wallet as WalletIcon, X,
} from "lucide-react";
import { SignInGate } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { mad } from "@/lib/data";
import { adminApi, downloadCsv, downloadAuditCsv } from "@/lib/admin";
import { metaBackendConfigured } from "@/lib/meta";
import logo from "@/assets/logo.png";

export const Route = createFileRoute("/admin")({
  head: () => ({
    meta: [
      { title: "Super Admin Control Center — ParkSpot AI" },
      { name: "description", content: "ParkSpot AI complete web administration control center." },
    ],
  }),
  component: AdminPage,
});

const SECTIONS = [
  { id: "overview", icon: LayoutDashboard, key: "aOverview" },
  { id: "users", icon: Users, key: "aUsers" },
  { id: "facilities", icon: Building2, key: "aFacilities" },
  { id: "bookings", icon: BookOpen, key: "aBookings" },
  { id: "pricing", icon: BarChart3, key: "aPricing" },
  { id: "ai", icon: Bot, key: "aAI" },
  { id: "cameras", icon: Camera, key: "aCameras" },
  { id: "payments", icon: WalletIcon, key: "aPayments" },
  { id: "reports", icon: FileText, key: "aReports" },
  { id: "incidents", icon: Bell, key: "aIncidents" },
  { id: "audit", icon: Activity, key: "aAudit" },
  { id: "database", icon: Database, key: "aDatabase" },
  { id: "settings", icon: SettingsIcon, key: "aSettings" },
] as const;

type SectionId = (typeof SECTIONS)[number]["id"];
type ConfirmState = { title: string; description?: string; run: (reason: string) => Promise<unknown> } | null;

const inputCls = "h-10 w-full rounded-xl border border-border/80 bg-background px-3 text-sm text-foreground outline-none transition-colors focus:border-primary focus:ring-1 focus:ring-primary";
const btnPrimaryCls = "inline-flex h-9 items-center justify-center gap-1.5 rounded-xl bg-primary px-3.5 text-xs font-semibold text-primary-foreground shadow-xs transition hover:bg-primary/90 disabled:opacity-50";
const btnGhostCls = "inline-flex h-9 items-center justify-center gap-1.5 rounded-xl border border-border/80 bg-card px-3 text-xs font-medium text-foreground transition hover:bg-muted/70 disabled:opacity-50";
const btnDestructiveCls = "inline-flex h-9 items-center justify-center gap-1.5 rounded-xl bg-destructive px-3.5 text-xs font-semibold text-destructive-foreground shadow-xs transition hover:bg-destructive/90 disabled:opacity-50";

function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-border/70 bg-card p-5 shadow-xs transition-shadow ${className}`}>{children}</div>;
}

function Badge({ children, variant = "default" }: { children: ReactNode; variant?: "default" | "success" | "warning" | "danger" | "info" | "purple" }) {
  const styles = {
    default: "bg-muted text-muted-foreground border-border/60",
    success: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800",
    warning: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
    danger: "bg-red-50 text-red-700 border-red-200 dark:bg-red-950/40 dark:text-red-300 dark:border-red-800",
    info: "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800",
    purple: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800",
  };
  return <span className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${styles[variant]}`}>{children}</span>;
}

function StatCard({ label, value, sub, icon: Icon, trend }: { label: string; value: ReactNode; sub?: ReactNode; icon?: typeof Users; trend?: "up" | "down" | "neutral" }) {
  return (
    <Card className="flex flex-col justify-between">
      <div className="flex items-start justify-between">
        <p className="text-xs font-medium text-muted-foreground">{label}</p>
        {Icon && <div className="rounded-xl bg-primary/10 p-2 text-primary"><Icon className="h-4 w-4" /></div>}
      </div>
      <div className="mt-2">
        <p className="text-2xl font-bold tracking-tight text-foreground">{value}</p>
        {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
      </div>
    </Card>
  );
}

function ConfirmModal({ state, close }: { state: ConfirmState; close: () => void }) {
  const { t } = useI18n();
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  if (!state) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true">
      <div className="w-full max-w-md rounded-2xl border border-border/80 bg-card p-6 shadow-xl animate-in fade-in zoom-in-95">
        <div className="flex items-center gap-2 text-primary">
          <ShieldAlert className="h-5 w-5" />
          <h3 className="font-display text-base font-semibold text-foreground">{state.title}</h3>
        </div>
        {state.description && <p className="mt-2 text-xs text-muted-foreground">{state.description}</p>}
        <label className="mt-4 block text-xs font-medium text-foreground">
          {t("reasonLbl")} <span className="text-destructive">*</span>
        </label>
        <textarea
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          rows={3}
          placeholder="Detailed administrative reason (minimum 3 characters)..."
          className="mt-1.5 w-full rounded-xl border border-border bg-background p-3 text-sm text-foreground outline-none focus:border-primary focus:ring-1 focus:ring-primary"
        />
        <p className="mt-1 text-end text-[11px] text-muted-foreground">{reason.trim().length}/3 chars min</p>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={() => { setReason(""); close(); }} className={btnGhostCls} disabled={busy}>{t("cancel")}</button>
          <button
            disabled={reason.trim().length < 3 || busy}
            className={btnPrimaryCls}
            onClick={async () => {
              setBusy(true);
              try {
                await state.run(reason.trim());
                toast.success(t("saved"));
                setReason("");
                close();
              } catch (e) {
                toast.error((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Processing..." : t("confirmAction")}
          </button>
        </div>
      </div>
    </div>
  );
}

function useSection<T>(key: string, fn: () => Promise<T>, enabled = true) {
  return useQuery({ queryKey: ["admin", key], queryFn: fn, enabled: enabled && metaBackendConfigured(), retry: false });
}

/* =========================================================================
   1. OVERVIEW — APPLICATION CONTROL CENTER
   ========================================================================= */
function Overview({ confirm, onNavigate }: { confirm: (s: ConfirmState) => void; onNavigate: (id: SectionId) => void }) {
  const { t, lang } = useI18n();
  const { data, isLoading, refetch, isFetching } = useSection("overview", adminApi.overview);
  const [daysFilter, setDaysFilter] = useState<number>(30);

  if (!metaBackendConfigured()) return <Card className="p-8 text-center text-muted-foreground">{t("backendOff")}</Card>;
  if (isLoading || !data) return <Card className="p-8 text-center text-muted-foreground">{t("transcribing")}</Card>;

  const pie = Object.entries(data.bookings_by_status ?? {}).map(([k, v]) => ({ name: k, value: v as number }));
  const STATUS_COLORS: Record<string, string> = {
    confirmed: "#059669",
    completed: "#2563eb",
    cancelled: "#dc2626",
    pending: "#d97706",
  };

  const utilizationRate = data.spaces_authorized > 0
    ? Math.round(((data.spaces_authorized - data.spaces_available) / data.spaces_authorized) * 100)
    : 0;

  return (
    <div className="space-y-6">
      {/* Top Banner: Real vs Demo Clarification */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-amber-300/60 bg-amber-50/70 p-4 text-xs text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-200">
        <div className="flex items-center gap-2">
          <Info className="h-4 w-4 shrink-0 text-amber-700" />
          <span>
            <b>Real Backend Operations:</b> User management, facility capacity constraints, bookings, camera operations, and pricing rules are connected live to the database.
            Revenue reflects simulated wallet transactions (demo environment).
          </span>
        </div>
        <button onClick={() => void refetch()} className={btnGhostCls} disabled={isFetching}>
          <RefreshCw className={`h-3.5 w-3.5 ${isFetching ? "animate-spin" : ""}`} />
          {t("refreshLbl")}
        </button>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={t("totalDrivers")}
          value={data.users_total}
          sub={`${data.users_suspended} ${t("suspendedUsers")}`}
          icon={Users}
        />
        <StatCard
          label={t("totalFacilitiesLbl")}
          value={`${data.facilities_active} / ${data.facilities_total}`}
          sub={`${data.spaces_authorized} authorized spaces`}
          icon={Building2}
        />
        <StatCard
          label={t("availableSpaces")}
          value={data.spaces_available}
          sub={`${utilizationRate}% occupancy`}
          icon={CheckCircle2}
        />
        <StatCard
          label={t("revenueDemo")}
          value={mad(data.revenue_cents, lang)}
          sub="Simulated demo ledger"
          icon={WalletIcon}
        />
      </div>

      {/* Operational Highlights */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">{t("activeBookings")}</p>
          <p className="mt-1 text-xl font-bold text-emerald-600">{data.bookings_by_status?.confirmed ?? 0}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">{t("completedBookings")}</p>
          <p className="mt-1 text-xl font-bold text-blue-600">{data.bookings_by_status?.completed ?? 0}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">{t("cancelledBookings")}</p>
          <p className="mt-1 text-xl font-bold text-red-600">{data.bookings_by_status?.cancelled ?? 0}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-muted-foreground">{t("camerasLbl")}</p>
          <p className="mt-1 text-xl font-bold text-foreground">{data.cameras_active} / {data.cameras_total} active</p>
        </Card>
      </div>

      {/* Charts Section */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <p className="font-semibold text-foreground">{t("bookingsPerDay")}</p>
            <Badge variant="default">Last 30 days</Badge>
          </div>
          <div className="h-64" dir="ltr">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.bookings_per_day}>
                <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="count" fill="#059669" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <p className="font-semibold text-foreground">{t("statusDistribution")}</p>
            <Badge variant="default">All reservations</Badge>
          </div>
          <div className="h-64" dir="ltr">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={pie} dataKey="value" nameKey="name" outerRadius={80} label>
                  {pie.map((entry) => (
                    <Cell key={entry.name} fill={STATUS_COLORS[entry.name] || "#64748b"} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* AI Services & Recent Audit Row */}
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <p className="font-semibold text-foreground">AI Services Status</p>
            <button onClick={() => onNavigate("ai")} className="text-xs text-primary hover:underline">{t("viewDetails")}</button>
          </div>
          <div className="space-y-2">
            {[
              { id: "muse_spark", label: "Muse Spark Assistant", data: data.ai_summary?.muse_spark },
              { id: "muse_voice", label: "Muse Voice Transcribe", data: data.ai_summary?.muse_voice },
              { id: "sam", label: "SAM 3.1 Vision Segmentation", data: data.ai_summary?.sam },
              { id: "easyocr", label: "EasyOCR License Plate Engine", data: data.ai_summary?.easyocr },
            ].map((svc) => (
              <div key={svc.id} className="flex items-center justify-between rounded-xl border border-border/60 bg-muted/30 p-2.5 text-xs">
                <span className="font-medium text-foreground">{svc.label}</span>
                <div className="flex items-center gap-2">
                  <Badge variant={svc.data?.configured ? "success" : "default"}>
                    {svc.data?.configured ? "Configured" : "Not Configured"}
                  </Badge>
                  <Badge variant={svc.data?.enabled ? "success" : "warning"}>
                    {svc.data?.enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center justify-between">
            <p className="font-semibold text-foreground">{t("recentActivity")}</p>
            <button onClick={() => onNavigate("audit")} className="text-xs text-primary hover:underline">{t("viewDetails")}</button>
          </div>
          {(data.recent_audit ?? []).length === 0 ? (
            <p className="text-xs text-muted-foreground">{t("noData")}</p>
          ) : (
            <ul className="divide-y divide-border/60 text-xs">
              {(data.recent_audit ?? []).slice(0, 5).map((a: { id: string; action: string; target_type: string; target_id?: string; created_at: string }) => (
                <li key={a.id} className="flex items-center justify-between py-2">
                  <div>
                    <span className="font-semibold text-foreground">{a.action}</span>
                    <span className="ms-2 text-muted-foreground">({a.target_type})</span>
                  </div>
                  <span className="text-[11px] text-muted-foreground">{new Date(a.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

/* =========================================================================
   2. USERS & ACCOUNTS MANAGEMENT
   ========================================================================= */
function UsersSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  const queryParams = new URLSearchParams({
    limit: "100",
    search: search.trim(),
    role: roleFilter,
    status: statusFilter,
  }).toString();

  const { data, isLoading } = useSection(`users-${queryParams}`, () => adminApi.users(queryParams));
  const { data: detailData, isLoading: detailLoading } = useSection(`user-detail-${selectedUserId}`, () => adminApi.userDetail(selectedUserId!), !!selectedUserId);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });
  const roleName = (r: string) => (r === "admin" ? t("roleAdmin") : r === "partner" ? t("rolePartner") : t("roleUser"));

  return (
    <div className="space-y-4">
      {/* Search & Filters */}
      <Card className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="absolute start-3 top-2.5 h-4 w-4 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={`${t("searchLbl")} by name, phone, plate, ID...`}
              className={`${inputCls} ps-9`}
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="h-10 rounded-xl border border-border/80 bg-background px-3 text-xs text-foreground outline-none"
            >
              <option value="">{t("allRoles")}</option>
              <option value="user">{t("roleUser")}</option>
              <option value="partner">{t("rolePartner")}</option>
              <option value="admin">{t("roleAdmin")}</option>
            </select>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-10 rounded-xl border border-border/80 bg-background px-3 text-xs text-foreground outline-none"
            >
              <option value="">{t("allStatuses")}</option>
              <option value="active">{t("active")}</option>
              <option value="suspended">{t("suspendedUsers")}</option>
            </select>
          </div>
        </div>
      </Card>

      {/* Users Table */}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-start text-xs font-medium text-muted-foreground">
              <th className="p-3.5 text-start">{t("name")}</th>
              <th className="p-3.5 text-start">{t("phone")} / {t("plate")}</th>
              <th className="p-3.5 text-start">Roles</th>
              <th className="p-3.5 text-start">{t("filterStatus")}</th>
              <th className="p-3.5 text-end">{t("actionsLbl")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {isLoading && (
              <tr><td colSpan={5} className="p-6 text-center text-xs text-muted-foreground">Loading accounts...</td></tr>
            )}
            {(data?.users ?? []).map((u: { id: string; display_name?: string; phone?: string; vehicle_plate?: string; vehicle_model?: string; status: string; roles: string[]; created_at: string }) => (
              <tr key={u.id} className="hover:bg-muted/20 transition-colors">
                <td className="p-3.5">
                  <p className="font-semibold text-foreground">{u.display_name || "Unnamed Driver"}</p>
                  <p className="font-mono text-[11px] text-muted-foreground">{u.id}</p>
                </td>
                <td className="p-3.5 text-xs text-foreground">
                  <p>{u.phone || "—"}</p>
                  <p className="text-muted-foreground">{u.vehicle_plate ? `${u.vehicle_plate} (${u.vehicle_model || "Car"})` : "No vehicle registered"}</p>
                </td>
                <td className="p-3.5">
                  <div className="flex flex-wrap gap-1">
                    {u.roles.map((r) => (
                      <Badge key={r} variant={r === "admin" ? "purple" : r === "partner" ? "info" : "default"}>
                        {roleName(r)}
                      </Badge>
                    ))}
                  </div>
                </td>
                <td className="p-3.5">
                  <Badge variant={u.status === "active" ? "success" : "danger"}>
                    {u.status}
                  </Badge>
                </td>
                <td className="p-3.5 text-end">
                  <div className="flex items-center justify-end gap-1.5">
                    <button
                      onClick={() => setSelectedUserId(u.id)}
                      className={btnGhostCls}
                      title={t("viewDetails")}
                    >
                      <Eye className="h-3.5 w-3.5" />
                      <span className="hidden sm:inline">{t("viewDetails")}</span>
                    </button>
                    {u.status === "active" ? (
                      <button
                        className={btnGhostCls}
                        onClick={() => confirm({
                          title: `${t("suspend")} — ${u.display_name || u.id.slice(0, 8)}`,
                          description: "The user will be blocked from making new bookings or accessing the wallet.",
                          run: async (r) => { await adminApi.suspendUser(u.id, r); invalidate(); },
                        })}
                      >
                        <UserX className="h-3.5 w-3.5 text-destructive" />
                        <span className="hidden sm:inline">{t("suspend")}</span>
                      </button>
                    ) : (
                      <button
                        className={btnGhostCls}
                        onClick={() => confirm({
                          title: `${t("reactivate")} — ${u.display_name || u.id.slice(0, 8)}`,
                          run: async (r) => { await adminApi.reactivateUser(u.id, r); invalidate(); },
                        })}
                      >
                        <UserCheck className="h-3.5 w-3.5 text-emerald-600" />
                        <span className="hidden sm:inline">{t("reactivate")}</span>
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.users.length === 0 && (
          <div className="p-8 text-center text-xs text-muted-foreground">{t("noData")}</div>
        )}
      </Card>

      {/* User Detail Modal */}
      {selectedUserId && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-2xl border border-border bg-card p-6 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-display text-lg font-semibold text-foreground">{t("userDetails")}</h3>
              <button onClick={() => setSelectedUserId(null)} className="rounded-lg p-1 text-muted-foreground hover:bg-muted"><X className="h-5 w-5" /></button>
            </div>
            {detailLoading || !detailData ? (
              <p className="p-6 text-center text-xs text-muted-foreground">Loading details...</p>
            ) : (
              <div className="mt-4 space-y-5 text-xs">
                {/* Account Summary */}
                <div className="grid grid-cols-2 gap-3 rounded-xl border border-border/80 bg-muted/20 p-4">
                  <div>
                    <p className="text-muted-foreground">{t("name")}</p>
                    <p className="font-semibold text-foreground">{detailData.profile?.display_name || "—"}</p>
                    <p className="mt-2 text-muted-foreground">User ID</p>
                    <p className="font-mono text-[11px] text-foreground">{detailData.profile?.id}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">{t("phone")}</p>
                    <p className="font-semibold text-foreground">{detailData.profile?.phone || "—"}</p>
                    <p className="mt-2 text-muted-foreground">{t("plate")} / {t("model")}</p>
                    <p className="font-semibold text-foreground">{detailData.profile?.vehicle_plate || "—"} {detailData.profile?.vehicle_model ? `(${detailData.profile?.vehicle_model})` : ""}</p>
                  </div>
                </div>

                {/* Role Management */}
                <div>
                  <p className="mb-2 font-semibold text-foreground">Role Provisioning</p>
                  <div className="flex flex-wrap gap-2">
                    {(["partner", "admin"] as const).map((role) => {
                      const hasRole = detailData.roles.includes(role);
                      return (
                        <button
                          key={role}
                          className={btnGhostCls}
                          onClick={() => confirm({
                            title: `${hasRole ? t("revokeRole") : t("grantRole")} ${roleName(role)}`,
                            description: `Modifying role permissions for ${detailData.profile?.display_name || detailData.profile?.id.slice(0, 8)}.`,
                            run: async (r) => {
                              await adminApi.setRole(detailData.profile.id, role, hasRole ? "revoke" : "grant", r);
                              invalidate();
                              setSelectedUserId(null);
                            },
                          })}
                        >
                          {hasRole ? <UserX className="h-3.5 w-3.5 text-destructive" /> : <UserPlus className="h-3.5 w-3.5 text-emerald-600" />}
                          {hasRole ? `${t("revokeRole")} ${roleName(role)}` : `${t("grantRole")} ${roleName(role)}`}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Wallet Balance */}
                {detailData.wallet && (
                  <div className="rounded-xl border border-border/80 p-3">
                    <p className="font-semibold text-foreground">{t("wallet")}</p>
                    <p className="mt-1 text-sm font-bold text-emerald-600">{mad(detailData.wallet.available_cents, "en")}</p>
                  </div>
                )}

                {/* Recent Bookings */}
                <div>
                  <p className="mb-2 font-semibold text-foreground">{t("aBookings")} ({detailData.bookings?.length ?? 0})</p>
                  <div className="max-h-48 overflow-y-auto rounded-xl border border-border/80">
                    <ul className="divide-y divide-border/60 text-[11px]">
                      {(detailData.bookings ?? []).map((b: { id: string; status: string; total_cents: number; start_at: string }) => (
                        <li key={b.id} className="flex items-center justify-between p-2.5">
                          <span>{b.id.slice(0, 8)}… · {new Date(b.start_at).toLocaleDateString()}</span>
                          <div className="flex items-center gap-2">
                            <span>{mad(b.total_cents, "en")}</span>
                            <Badge variant={b.status === "confirmed" ? "success" : b.status === "cancelled" ? "danger" : "default"}>{b.status}</Badge>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   3. PARKING FACILITY MANAGEMENT
   ========================================================================= */
function FacilitiesSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("facilities", adminApi.facilities);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });

  const [modalMode, setModalMode] = useState<"create" | "edit" | null>(null);
  const [activeFacility, setActiveFacility] = useState<any | null>(null);

  const [form, setForm] = useState({
    name: "", name_ar: "", city: "Casablanca", address: "",
    lat: 33.59, lng: -7.62, price: 1500, total: 100, authorized: 50, available: 50,
  });

  const openCreate = () => {
    setForm({
      name: "", name_ar: "", city: "Casablanca", address: "",
      lat: 33.59, lng: -7.62, price: 1500, total: 100, authorized: 50, available: 50,
    });
    setModalMode("create");
  };

  const openEdit = (f: any) => {
    setActiveFacility(f);
    setForm({
      name: f.name, name_ar: f.name_ar || "", city: f.city || "Casablanca",
      address: f.address || "", lat: f.lat || 33.59, lng: f.lng || -7.62,
      price: f.price_per_hour_cents || 1500, total: f.total_capacity || 100,
      authorized: f.authorized_capacity || 50, available: f.available || 50,
    });
    setModalMode("edit");
  };

  const handleSubmit = async () => {
    // Capacity invariants
    if (form.authorized > form.total) {
      toast.error("Authorized capacity cannot exceed total physical capacity.");
      return;
    }
    if (form.available > form.authorized) {
      toast.error("Available spaces cannot exceed authorized capacity.");
      return;
    }
    try {
      if (modalMode === "create") {
        await adminApi.createFacility({
          name: form.name, name_ar: form.name_ar, city: form.city, address: form.address,
          lat: form.lat, lng: form.lng, price_per_hour_cents: form.price,
          total_capacity: form.total, authorized_capacity: form.authorized, available: form.available,
          features: ["covered", "security_guard"], open_24h: true, active: true,
        });
        toast.success(t("saved"));
      } else if (modalMode === "edit" && activeFacility) {
        confirm({
          title: `${t("editFacility")} — ${form.name}`,
          description: "Capacity and details updates will immediately take effect for driver bookings.",
          run: async (reason) => {
            await adminApi.updateFacility(activeFacility.id, {
              name: form.name, name_ar: form.name_ar, city: form.city, address: form.address,
              lat: form.lat, lng: form.lng, price_per_hour_cents: form.price,
              total_capacity: form.total, authorized_capacity: form.authorized, available: form.available,
              reason,
            });
            invalidate();
          },
        });
      }
      setModalMode(null);
      invalidate();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header & Add Button */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">Contracted facility agreements & inventory boundaries</p>
        <button onClick={openCreate} className={btnPrimaryCls}>
          <Plus className="h-4 w-4" />
          {t("newFacility")}
        </button>
      </div>

      {/* Facilities Table */}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-start text-xs font-medium text-muted-foreground">
              <th className="p-3.5 text-start">{t("name")}</th>
              <th className="p-3.5 text-start">Address</th>
              <th className="p-3.5 text-start">{t("totalCapacityLbl")}</th>
              <th className="p-3.5 text-start">{t("authorizedCapacityLbl")}</th>
              <th className="p-3.5 text-start">{t("availableSpaces")}</th>
              <th className="p-3.5 text-start">{t("filterStatus")}</th>
              <th className="p-3.5 text-end">{t("actionsLbl")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {(data?.facilities ?? []).map((f: any) => {
              const occRate = f.authorized_capacity > 0 ? Math.round(((f.authorized_capacity - f.available) / f.authorized_capacity) * 100) : 0;
              return (
                <tr key={f.id} className="hover:bg-muted/20 transition-colors">
                  <td className="p-3.5">
                    <p className="font-semibold text-foreground">{f.name}</p>
                    <p className="text-[11px] text-muted-foreground">{f.name_ar || f.city}</p>
                  </td>
                  <td className="p-3.5 text-xs text-muted-foreground">{f.address}</td>
                  <td className="p-3.5 text-xs font-semibold">{f.total_capacity}</td>
                  <td className="p-3.5 text-xs font-semibold text-primary">{f.authorized_capacity}</td>
                  <td className="p-3.5 text-xs">
                    <span className="font-semibold">{f.available}</span>
                    <span className="ms-1 text-muted-foreground">({occRate}% occ)</span>
                  </td>
                  <td className="p-3.5">
                    <Badge variant={f.active ? "success" : "danger"}>
                      {f.active ? t("enabledLbl") : t("disabledLbl")}
                    </Badge>
                  </td>
                  <td className="p-3.5 text-end">
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => openEdit(f)} className={btnGhostCls}>
                        {t("editFacility")}
                      </button>
                      <button
                        className={btnGhostCls}
                        onClick={() => confirm({
                          title: `${f.active ? t("disabledLbl") : t("enabledLbl")} — ${f.name}`,
                          description: f.active ? "Deactivating prevents new bookings; existing reservations remain intact." : "Activating opens booking availability.",
                          run: async (r) => {
                            await adminApi.updateFacility(f.id, { active: !f.active, reason: r });
                            invalidate();
                          },
                        })}
                      >
                        {f.active ? t("disabledLbl") : t("enabledLbl")}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      {/* Facility Form Modal */}
      {modalMode && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true">
          <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-border bg-card p-6 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-display text-base font-semibold text-foreground">
                {modalMode === "create" ? t("newFacility") : t("editFacility")}
              </h3>
              <button onClick={() => setModalMode(null)} className="rounded-lg p-1 text-muted-foreground hover:bg-muted"><X className="h-5 w-5" /></button>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
              <div className="col-span-2 sm:col-span-1">
                <label className="block text-muted-foreground">Facility Name (EN)</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputCls} />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label className="block text-muted-foreground">Facility Name (AR)</label>
                <input value={form.name_ar} onChange={(e) => setForm({ ...form, name_ar: e.target.value })} className={inputCls} />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label className="block text-muted-foreground">City</label>
                <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} className={inputCls} />
              </div>
              <div className="col-span-2 sm:col-span-1">
                <label className="block text-muted-foreground">Address</label>
                <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="block text-muted-foreground">Latitude</label>
                <input type="number" step="0.0001" value={form.lat} onChange={(e) => setForm({ ...form, lat: Number(e.target.value) })} className={inputCls} />
              </div>
              <div>
                <label className="block text-muted-foreground">Longitude</label>
                <input type="number" step="0.0001" value={form.lng} onChange={(e) => setForm({ ...form, lng: Number(e.target.value) })} className={inputCls} />
              </div>
              <div className="col-span-2">
                <label className="block text-muted-foreground">{t("priceCents")}</label>
                <input type="number" value={form.price} onChange={(e) => setForm({ ...form, price: Number(e.target.value) })} className={inputCls} />
              </div>
              <div>
                <label className="block text-muted-foreground">{t("totalCapacityLbl")}</label>
                <input type="number" value={form.total} onChange={(e) => setForm({ ...form, total: Number(e.target.value) })} className={inputCls} />
              </div>
              <div>
                <label className="block text-muted-foreground">{t("authorizedCapacityLbl")}</label>
                <input type="number" value={form.authorized} onChange={(e) => setForm({ ...form, authorized: Number(e.target.value) })} className={inputCls} />
              </div>
              <div className="col-span-2">
                <label className="block text-muted-foreground">{t("availableSpaces")}</label>
                <input type="number" value={form.available} onChange={(e) => setForm({ ...form, available: Number(e.target.value) })} className={inputCls} />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2 border-t pt-4">
              <button onClick={() => setModalMode(null)} className={btnGhostCls}>{t("cancel")}</button>
              <button onClick={handleSubmit} className={btnPrimaryCls}>{t("save")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   4. BOOKINGS & RESERVATIONS MANAGEMENT
   ========================================================================= */
function BookingsSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [selectedBooking, setSelectedBooking] = useState<any | null>(null);

  const queryParams = new URLSearchParams({
    limit: "100",
    status,
    search: search.trim(),
  }).toString();

  const { data, isLoading } = useSection(`bookings-${queryParams}`, () => adminApi.bookings(queryParams));
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute start-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search booking ID, user, or facility..."
            className={`${inputCls} ps-9`}
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {["", "confirmed", "completed", "cancelled"].map((s) => (
            <button
              key={s}
              onClick={() => setStatus(s)}
              className={status === s ? btnPrimaryCls : btnGhostCls}
            >
              {s ? s.charAt(0).toUpperCase() + s.slice(1) : "All Statuses"}
            </button>
          ))}
        </div>
      </Card>

      {/* Bookings Table */}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-start text-xs font-medium text-muted-foreground">
              <th className="p-3.5 text-start">Booking ID & Date</th>
              <th className="p-3.5 text-start">Facility</th>
              <th className="p-3.5 text-start">Schedule</th>
              <th className="p-3.5 text-start">{t("total")}</th>
              <th className="p-3.5 text-start">{t("filterStatus")}</th>
              <th className="p-3.5 text-end">{t("actionsLbl")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {isLoading && (
              <tr><td colSpan={6} className="p-6 text-center text-xs text-muted-foreground">Loading reservations...</td></tr>
            )}
            {(data?.bookings ?? []).map((b: any) => (
              <tr key={b.id} className="hover:bg-muted/20 transition-colors">
                <td className="p-3.5">
                  <p className="font-mono text-xs font-semibold text-foreground">{b.id.slice(0, 8)}…</p>
                  <p className="text-[11px] text-muted-foreground">{new Date(b.created_at).toLocaleString()}</p>
                </td>
                <td className="p-3.5 text-xs">
                  <p className="font-medium text-foreground">{b.facility_name || "—"}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">{b.user_id.slice(0, 8)}…</p>
                </td>
                <td className="p-3.5 text-xs text-muted-foreground">
                  {new Date(b.start_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} – {new Date(b.end_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} ({b.hours}h)
                </td>
                <td className="p-3.5 text-xs font-semibold text-foreground">
                  {mad(b.total_cents, lang)}
                  {b.refunded_cents > 0 && <span className="ms-1 text-red-500 font-normal">(-{mad(b.refunded_cents, lang)})</span>}
                </td>
                <td className="p-3.5">
                  <Badge variant={b.status === "confirmed" ? "success" : b.status === "completed" ? "info" : "danger"}>
                    {b.status}
                  </Badge>
                </td>
                <td className="p-3.5 text-end">
                  <div className="flex items-center justify-end gap-1.5">
                    <button onClick={() => setSelectedBooking(b)} className={btnGhostCls}>
                      <Eye className="h-3.5 w-3.5" />
                    </button>
                    {b.status === "confirmed" && (
                      <button
                        className={btnGhostCls}
                        onClick={() => confirm({
                          title: `${t("cancel")} — ${b.id.slice(0, 8)}`,
                          description: "Automated cancellation recalculates refund according to policy and restores 1 authorized space.",
                          run: async (r) => {
                            await adminApi.cancelBooking(b.id, r);
                            invalidate();
                          },
                        })}
                      >
                        {t("cancel")}
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.bookings.length === 0 && (
          <div className="p-8 text-center text-xs text-muted-foreground">{t("noData")}</div>
        )}
      </Card>

      {/* Booking Detail Modal */}
      {selectedBooking && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true">
          <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-display text-base font-semibold text-foreground">{t("bookingDetails")}</h3>
              <button onClick={() => setSelectedBooking(null)} className="rounded-lg p-1 text-muted-foreground hover:bg-muted"><X className="h-5 w-5" /></button>
            </div>
            <div className="mt-4 space-y-3 text-xs">
              <div className="rounded-xl border border-border/80 bg-muted/20 p-3">
                <p className="text-muted-foreground">Booking ID</p>
                <p className="font-mono text-xs font-semibold text-foreground">{selectedBooking.id}</p>
                <p className="mt-2 text-muted-foreground">Driver User ID</p>
                <p className="font-mono text-xs text-foreground">{selectedBooking.user_id}</p>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-muted-foreground">Start Time</p>
                  <p className="font-medium text-foreground">{new Date(selectedBooking.start_at).toLocaleString()}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">End Time</p>
                  <p className="font-medium text-foreground">{new Date(selectedBooking.end_at).toLocaleString()}</p>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-muted-foreground">{t("total")}</p>
                  <p className="text-base font-bold text-foreground">{mad(selectedBooking.total_cents, lang)}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Access Code</p>
                  <p className="font-mono text-base font-bold text-primary">{selectedBooking.access_code || "1234"}</p>
                </div>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2 border-t pt-4">
              <button onClick={() => setSelectedBooking(null)} className={btnGhostCls}>{t("close")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   5. PRICING MANAGEMENT
   ========================================================================= */
function PricingSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const { data, refetch } = useSection("pricing", adminApi.pricing);
  const [prices, setPrices] = useState<Record<string, string>>({});
  const [isRecomputing, setIsRecomputing] = useState(false);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });

  const handleRecompute = async () => {
    setIsRecomputing(true);
    try {
      await adminApi.recomputePricing();
      toast.success("Dynamic pricing recommendation recalculated based on current occupancy.");
      await refetch();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setIsRecomputing(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Control Strip */}
      <Card className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="font-semibold text-foreground">Dynamic Pricing Rules</p>
          <p className="text-xs text-muted-foreground">
            Allowable bounds: {data?.pricing_min_cents}–{data?.pricing_max_cents} cents/hr · Engine: {data?.engine}
          </p>
        </div>
        <button onClick={handleRecompute} disabled={isRecomputing} className={btnPrimaryCls}>
          <Sparkles className={`h-4 w-4 ${isRecomputing ? "animate-spin" : ""}`} />
          {t("recomputePricing")}
        </button>
      </Card>

      {/* Facilities Pricing Table */}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-start text-xs font-medium text-muted-foreground">
              <th className="p-3.5 text-start">{t("name")}</th>
              <th className="p-3.5 text-start">{t("occupancyRate")}</th>
              <th className="p-3.5 text-start">{t("appliedPrice")}</th>
              <th className="p-3.5 text-start">{t("recommendedPrice")}</th>
              <th className="p-3.5 text-start">{t("aiSuggestedPrice")}</th>
              <th className="p-3.5 text-end">{t("actionsLbl")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {(data?.facilities ?? []).map((f: any) => {
              const currentInput = prices[f.id] ?? String(f.price_per_hour_cents);
              const recCents = f.heuristic_recommended_cents || f.price_per_hour_cents;
              const aiCents = f.ai_suggested_cents || f.price_per_hour_cents;
              return (
                <tr key={f.id} className="hover:bg-muted/20 transition-colors">
                  <td className="p-3.5 font-semibold text-foreground">
                    {f.name}
                    <p className="text-[11px] font-normal text-muted-foreground">{f.city}</p>
                  </td>
                  <td className="p-3.5 text-xs text-muted-foreground">
                    {Math.round((f.occupancy_rate || 0) * 100)}%
                  </td>
                  <td className="p-3.5">
                    <div className="flex items-center gap-1.5">
                      <input
                        type="number"
                        className="h-8 w-24 rounded-lg border border-border/80 bg-background px-2 text-xs"
                        value={currentInput}
                        onChange={(e) => setPrices({ ...prices, [f.id]: e.target.value })}
                      />
                      <span className="text-xs text-muted-foreground">{mad(Number(currentInput), lang)}/h</span>
                    </div>
                  </td>
                  <td className="p-3.5 text-xs">
                    <span className="font-semibold text-emerald-600">{mad(recCents, lang)}</span>
                    <button
                      onClick={() => setPrices({ ...prices, [f.id]: String(recCents) })}
                      className="ms-2 text-[10px] text-primary hover:underline"
                    >
                      Use
                    </button>
                  </td>
                  <td className="p-3.5 text-xs">
                    <span className="font-semibold text-purple-600">{mad(aiCents, lang)}</span>
                    <button
                      onClick={() => setPrices({ ...prices, [f.id]: String(aiCents) })}
                      className="ms-2 text-[10px] text-purple-600 hover:underline"
                    >
                      Use
                    </button>
                  </td>
                  <td className="p-3.5 text-end">
                    <button
                      className={btnPrimaryCls}
                      onClick={() => confirm({
                        title: `${t("save")} — ${f.name}`,
                        description: `Applying authoritative price of ${mad(Number(currentInput), lang)}/hour.`,
                        run: async (r) => {
                          await adminApi.setPrice(f.id, Number(currentInput), r);
                          invalidate();
                        },
                      })}
                    >
                      {t("save")}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      {/* Pricing Audit History */}
      <Card>
        <p className="mb-3 font-semibold text-foreground">{t("pricingHistory")}</p>
        {(data?.history ?? []).length === 0 ? (
          <p className="text-xs text-muted-foreground">{t("noData")}</p>
        ) : (
          <ul className="divide-y divide-border/60 text-xs">
            {(data?.history ?? []).map((h: any) => (
              <li key={h.id} className="flex items-center justify-between py-2">
                <span>Updated facility rate to <b>{mad(h.metadata?.price_per_hour_cents ?? 0, lang)}</b> — <i>{h.reason || "No reason"}</i></span>
                <span className="text-[11px] text-muted-foreground">{new Date(h.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

/* =========================================================================
   6. AI MANAGEMENT CENTER
   ========================================================================= */
function AiSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("ai", adminApi.aiStatus);
  const healthMutation = useMutation({ mutationFn: (s: string) => adminApi.aiHealth(s) });

  const services = data?.services ?? {};
  const metrics = data?.metrics?.services ?? {};

  const serviceDefs = [
    { id: "muse_spark", label: "Muse Spark Assistant", feature: "assistant", desc: "Meta LLaMA model powering natural language search & parking guidance" },
    { id: "muse_voice", label: "Muse Voice Transcribe", feature: "voice", desc: "Audio transcription for hands-free voice search" },
    { id: "sam", label: "SAM 3.1 Vision Segmentation", feature: "vision", desc: "Spatial vision model locating vehicles and plates in camera streams" },
    { id: "easyocr", label: "EasyOCR License Plate Recognition", feature: "vision", desc: "Optical character recognition reading vehicle license plates" },
  ];

  return (
    <div className="space-y-4">
      <Card className="flex items-center justify-between border-emerald-300/60 bg-emerald-50/50 p-4 text-xs text-emerald-950 dark:border-emerald-900/60 dark:bg-emerald-950/20 dark:text-emerald-200">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-emerald-700" />
          <span><b>Security First:</b> Safe predefined probes verify network reachability without inference or secret leakage. API keys remain secret server-side.</span>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {serviceDefs.map((def) => {
          const s = services[def.id] ?? {};
          const m = metrics[def.id] ?? {};
          const probeRes = healthMutation.data && healthMutation.variables === def.id ? healthMutation.data : null;

          return (
            <Card key={def.id} className="flex flex-col justify-between">
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="font-semibold text-foreground">{def.label}</p>
                    <p className="text-[11px] text-muted-foreground">{def.desc}</p>
                  </div>
                  <Badge variant={s.enabled ? "success" : "default"}>
                    {s.enabled ? t("enabledLbl") : t("disabledLbl")}
                  </Badge>
                </div>

                <div className="mt-4 space-y-2 rounded-xl border border-border/60 bg-muted/20 p-3 text-xs">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">{t("configuredLbl")}:</span>
                    <span className="font-medium">{s.configured ? "✓ Configured" : "— Not Configured"} {s.model ? `(${s.model})` : ""}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Requests / Errors:</span>
                    <span>{m.requests ?? 0} requests · {m.errors ?? 0} errors {m.avg_latency_ms ? `· ${m.avg_latency_ms}ms avg` : ""}</span>
                  </div>
                  {m.last_error && (
                    <div className="flex justify-between gap-2 text-destructive">
                      <span className="shrink-0">Last error:</span>
                      <span className="truncate">{m.last_error}</span>
                    </div>
                  )}
                  {probeRes && (
                    <div className="mt-2 rounded-lg border border-border bg-card p-2">
                      <p className="font-semibold text-foreground">Health Check Result:</p>
                      <p className="text-[11px] text-muted-foreground">{probeRes.detail}</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="mt-4 flex items-center justify-end gap-2 border-t pt-3">
                <button
                  disabled={healthMutation.isPending}
                  onClick={() => healthMutation.mutate(def.id)}
                  className={btnGhostCls}
                >
                  <RefreshCw className={`h-3.5 w-3.5 ${healthMutation.isPending && healthMutation.variables === def.id ? "animate-spin" : ""}`} />
                  {t("healthCheck")}
                </button>
                <button
                  className={btnGhostCls}
                  onClick={() => confirm({
                    title: `${def.label}: ${s.enabled ? t("disabledLbl") : t("enabledLbl")}`,
                    description: `Toggling feature flag ${def.feature}.`,
                    run: async (r) => {
                      await adminApi.aiToggle(def.feature, !s.enabled, r);
                      qc.invalidateQueries({ queryKey: ["admin"] });
                    },
                  })}
                >
                  {s.enabled ? t("disabledLbl") : t("enabledLbl")}
                </button>
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

/* =========================================================================
   7. CAMERAS & ACCESS CONTROL
   ========================================================================= */
function CamerasSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("cameras", adminApi.cameras);
  const [modalOpen, setModalOpen] = useState(false);
  const [label, setLabel] = useState("");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">ANPR camera stations & server-side access verification events</p>
        <button onClick={() => setModalOpen(true)} className={btnPrimaryCls}>
          <Plus className="h-4 w-4" />
          {t("registerCamera")}
        </button>
      </div>

      {/* Cameras Table */}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-start text-xs font-medium text-muted-foreground">
              <th className="p-3.5 text-start">Camera Label</th>
              <th className="p-3.5 text-start">Assigned Facility</th>
              <th className="p-3.5 text-start">{t("filterStatus")}</th>
              <th className="p-3.5 text-end">{t("actionsLbl")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {(data?.cameras ?? []).map((cam: any) => (
              <tr key={cam.id} className="hover:bg-muted/20 transition-colors">
                <td className="p-3.5">
                  <p className="font-semibold text-foreground">{cam.label}</p>
                  <p className="font-mono text-[10px] text-muted-foreground">{cam.id}</p>
                </td>
                <td className="p-3.5 text-xs text-muted-foreground">{cam.facility_id || "Unassigned"}</td>
                <td className="p-3.5">
                  <Badge variant={cam.status === "active" ? "success" : "default"}>{cam.status}</Badge>
                </td>
                <td className="p-3.5 text-end">
                  <button
                    className={btnGhostCls}
                    onClick={() => confirm({
                      title: `${cam.label}: ${cam.status === "active" ? t("disabledLbl") : t("enabledLbl")}`,
                      run: async (r) => {
                        await adminApi.updateCamera(cam.id, { status: cam.status === "active" ? "inactive" : "active", reason: r });
                        invalidate();
                      },
                    })}
                  >
                    {cam.status === "active" ? t("disabledLbl") : t("enabledLbl")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {/* Camera Access Events Stream */}
      <Card>
        <p className="mb-3 font-semibold text-foreground">{t("cameraEvents")}</p>
        {(data?.events ?? []).length === 0 ? (
          <p className="text-xs text-muted-foreground">{t("noData")}</p>
        ) : (
          <ul className="divide-y divide-border/60 text-xs">
            {(data?.events ?? []).map((e: any) => (
              <li key={e.id} className="flex items-center justify-between py-2.5">
                <div className="flex items-center gap-2">
                  <Badge variant={e.access_result === "verified" ? "success" : "default"}>
                    {e.kind}
                  </Badge>
                  <span className="font-medium text-foreground">{e.access_result || "Processed"}</span>
                  {e.ocr_confidence && <span className="text-muted-foreground">({Math.round(Number(e.ocr_confidence) * 100)}% OCR)</span>}
                  {e.simulated && <Badge variant="warning">SIMULATED</Badge>}
                </div>
                <span className="text-[11px] text-muted-foreground">{new Date(e.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Register Camera Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true">
          <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl animate-in fade-in zoom-in-95">
            <h3 className="font-display text-base font-semibold text-foreground">{t("registerCamera")}</h3>
            <div className="mt-4 space-y-3">
              <div>
                <label className="text-xs text-muted-foreground">Station / Gate Label</label>
                <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. Marina Entry Gate 1" className={inputCls} />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => setModalOpen(false)} className={btnGhostCls}>{t("cancel")}</button>
              <button
                disabled={label.trim().length < 2}
                className={btnPrimaryCls}
                onClick={async () => {
                  try {
                    await adminApi.createCamera({ label: label.trim(), status: "active" });
                    toast.success(t("saved"));
                    setLabel("");
                    setModalOpen(false);
                    invalidate();
                  } catch (e) {
                    toast.error((e as Error).message);
                  }
                }}
              >
                {t("createLbl")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   8. PAYMENTS & WALLET MANAGEMENT
   ========================================================================= */
function PaymentsSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t, lang } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("wallets", adminApi.wallets);
  const [selectedUser, setSelectedUser] = useState<string | null>(null);
  const { data: txData } = useSection(`tx-${selectedUser}`, () => adminApi.walletTx(selectedUser!), !!selectedUser);
  const [amount, setAmount] = useState("");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });

  return (
    <div className="space-y-4">
      {/* Demo Warning Banner */}
      <Card className="border-amber-300/80 bg-amber-50/70 p-4 text-xs text-amber-950 dark:border-amber-900 dark:bg-amber-950/20 dark:text-amber-200">
        <p className="font-semibold">{t("demoBanner")}</p>
        <p className="mt-0.5 text-amber-800 dark:text-amber-300">
          All wallet credits, debits, and adjustments move through SECURITY DEFINER PostgreSQL functions (admin_adjust_wallet). Balances cannot be forged or go negative.
        </p>
      </Card>

      {/* Wallets Table */}
      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-start text-xs font-medium text-muted-foreground">
              <th className="p-3.5 text-start">{t("name")}</th>
              <th className="p-3.5 text-start">{t("available")}</th>
              <th className="p-3.5 text-end">{t("actionsLbl")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {(data?.wallets ?? []).map((w: any) => (
              <tr key={w.user_id} className="hover:bg-muted/20 transition-colors">
                <td className="p-3.5">
                  <p className="font-semibold text-foreground">{w.display_name || "Driver"}</p>
                  <p className="font-mono text-[11px] text-muted-foreground">{w.user_id}</p>
                </td>
                <td className="p-3.5 text-sm font-bold text-emerald-600">
                  {mad(w.available_cents, lang)}
                </td>
                <td className="p-3.5 text-end">
                  <button onClick={() => setSelectedUser(w.user_id)} className={btnGhostCls}>
                    <Eye className="h-3.5 w-3.5" />
                    {t("history")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      {/* Ledger & Adjustment Drawer */}
      {selectedUser && (
        <Card className="space-y-4">
          <div className="flex items-center justify-between border-b pb-3">
            <div>
              <p className="font-semibold text-foreground">Wallet Ledger & Balance Adjustment</p>
              <p className="font-mono text-xs text-muted-foreground">User ID: {selectedUser}</p>
            </div>
            <button onClick={() => setSelectedUser(null)} className="rounded-lg p-1 text-muted-foreground hover:bg-muted"><X className="h-5 w-5" /></button>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              type="number"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Amount in cents (e.g. 5000 = 50 MAD, -2000 = -20 MAD)"
              className={inputCls}
            />
            <button
              disabled={!amount || Number(amount) === 0}
              className={btnPrimaryCls}
              onClick={() => confirm({
                title: `${t("adjustBalance")} for ${selectedUser.slice(0, 8)}`,
                description: `Adjusting wallet balance by ${amount} cents. Balances cannot become negative.`,
                run: async (r) => {
                  await adminApi.adjustWallet(selectedUser, Number(amount), r);
                  setAmount("");
                  invalidate();
                },
              })}
            >
              {t("adjustBalance")}
            </button>
          </div>

          <p className="font-semibold text-xs text-foreground mt-4">{t("recent")}</p>
          <ul className="divide-y divide-border/60 text-xs">
            {(txData?.transactions ?? []).map((tx: any) => (
              <li key={tx.id} className="flex items-center justify-between py-2">
                <div>
                  <span className="font-medium text-foreground">{tx.type}</span>
                  <span className="ms-2 text-muted-foreground">({tx.description || tx.status})</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`font-semibold ${tx.amount_cents >= 0 ? "text-emerald-600" : "text-foreground"}`}>
                    {tx.amount_cents >= 0 ? "+" : ""}{mad(tx.amount_cents, lang)}
                  </span>
                  <span className="text-[10px] text-muted-foreground">{new Date(tx.created_at).toLocaleDateString()}</span>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

/* =========================================================================
   9. REPORTS & ANALYTICS
   ========================================================================= */
function ReportsSection() {
  const { t, lang } = useI18n();
  const [days, setDays] = useState(30);
  const { data } = useSection(`reports-${days}`, () => adminApi.reports(days));

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex gap-1.5">
          {[7, 30, 90].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={days === d ? btnPrimaryCls : btnGhostCls}
            >
              {d} Days
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <button onClick={() => void downloadCsv().catch((e) => toast.error((e as Error).message))} className={btnGhostCls}>
            <Download className="h-3.5 w-3.5" />
            {t("exportCsv")}
          </button>
          <button onClick={() => void downloadAuditCsv().catch((e) => toast.error((e as Error).message))} className={btnGhostCls}>
            <Download className="h-3.5 w-3.5" />
            {t("exportAuditCsv")}
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <StatCard label="Total Reservations" value={data?.total ?? 0} icon={BookOpen} />
        <StatCard label={t("cancelled")} value={data?.cancelled ?? 0} icon={AlertCircle} />
        <StatCard label="Cancellation Rate" value={`${Math.round((data?.cancellation_rate ?? 0) * 100)}%`} icon={Activity} />
      </div>

      {/* Chart: Bookings Over Time */}
      <Card>
        <p className="mb-4 font-semibold text-foreground">{t("bookingsPerDay")}</p>
        <div className="h-64" dir="ltr">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data?.bookings_per_day ?? []}>
              <XAxis dataKey="date" tick={{ fontSize: 10 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#059669" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Facility Performance */}
      <Card>
        <p className="mb-3 font-semibold text-foreground">Facility Booking & Revenue Performance</p>
        <ul className="divide-y divide-border/60 text-xs">
          {(data?.facility_performance ?? []).map((f: any) => (
            <li key={f.facility_id} className="flex items-center justify-between py-2.5">
              <span className="font-medium text-foreground">{f.name || f.facility_id.slice(0, 8)}</span>
              <div className="flex items-center gap-3">
                <span className="text-muted-foreground">{f.bookings} bookings</span>
                <span className="font-semibold text-foreground">{mad(f.revenue_cents, lang)}</span>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

/* =========================================================================
   10. NOTIFICATIONS & INCIDENTS
   ========================================================================= */
function IncidentsSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const { data } = useSection(`incidents-${status}`, () => adminApi.incidents(status));
  const [modalOpen, setModalOpen] = useState(false);
  const [newIncident, setNewIncident] = useState({ title: "", kind: "user_report", details: "" });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin"] });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-1.5">
          {["", "open", "investigating", "resolved"].map((st) => (
            <button key={st} onClick={() => setStatus(st)} className={status === st ? btnPrimaryCls : btnGhostCls}>
              {st ? st.charAt(0).toUpperCase() + st.slice(1) : "All Incidents"}
            </button>
          ))}
        </div>
        <button onClick={() => setModalOpen(true)} className={btnPrimaryCls}>
          <Plus className="h-4 w-4" />
          Report Incident
        </button>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[640px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-start text-xs font-medium text-muted-foreground">
              <th className="p-3.5 text-start">Incident</th>
              <th className="p-3.5 text-start">Category</th>
              <th className="p-3.5 text-start">{t("filterStatus")}</th>
              <th className="p-3.5 text-end">{t("actionsLbl")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {(data?.incidents ?? []).map((i: any) => (
              <tr key={i.id} className="hover:bg-muted/20 transition-colors">
                <td className="p-3.5">
                  <p className="font-semibold text-foreground">{i.title}</p>
                  <p className="text-[11px] text-muted-foreground">{i.details || "No details provided"}</p>
                </td>
                <td className="p-3.5">
                  <Badge variant="default">{i.kind}</Badge>
                </td>
                <td className="p-3.5">
                  <Badge variant={i.status === "open" ? "danger" : i.status === "investigating" ? "warning" : "success"}>
                    {i.status}
                  </Badge>
                </td>
                <td className="p-3.5 text-end">
                  <div className="flex items-center justify-end gap-1">
                    {(["investigating", "resolved", "dismissed"] as const).map((s) => (
                      <button
                        key={s}
                        className={btnGhostCls}
                        onClick={() => confirm({
                          title: `Update incident to ${s}`,
                          run: async (r) => {
                            await adminApi.updateIncident(i.id, s, r);
                            invalidate();
                          },
                        })}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.incidents.length === 0 && (
          <div className="p-8 text-center text-xs text-muted-foreground">{t("noData")}</div>
        )}
      </Card>

      {/* Create Incident Modal */}
      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true">
          <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl animate-in fade-in zoom-in-95">
            <h3 className="font-display text-base font-semibold text-foreground">Report New Incident</h3>
            <div className="mt-4 space-y-3 text-xs">
              <div>
                <label className="text-muted-foreground">Title</label>
                <input value={newIncident.title} onChange={(e) => setNewIncident({ ...newIncident, title: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="text-muted-foreground">Category</label>
                <select
                  value={newIncident.kind}
                  onChange={(e) => setNewIncident({ ...newIncident, kind: e.target.value })}
                  className="h-10 w-full rounded-xl border border-border bg-background px-3 text-xs text-foreground outline-none"
                >
                  <option value="user_report">User Report</option>
                  <option value="booking_complaint">Booking Complaint</option>
                  <option value="facility">Facility Incident</option>
                  <option value="camera">Camera Incident</option>
                  <option value="system">System Alert</option>
                  <option value="ai_error">AI Service Error</option>
                </select>
              </div>
              <div>
                <label className="text-muted-foreground">Details</label>
                <textarea rows={3} value={newIncident.details} onChange={(e) => setNewIncident({ ...newIncident, details: e.target.value })} className="w-full rounded-xl border border-border bg-background p-2.5 text-xs text-foreground outline-none" />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button onClick={() => setModalOpen(false)} className={btnGhostCls}>{t("cancel")}</button>
              <button
                disabled={newIncident.title.trim().length < 3}
                className={btnPrimaryCls}
                onClick={async () => {
                  try {
                    await adminApi.createIncident(newIncident);
                    toast.success(t("saved"));
                    setModalOpen(false);
                    invalidate();
                  } catch (e) {
                    toast.error((e as Error).message);
                  }
                }}
              >
                {t("createLbl")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   11. AUDIT LOGS
   ========================================================================= */
function AuditSection() {
  const { t } = useI18n();
  const [action, setAction] = useState("");
  const { data } = useSection(`audit-${action}`, () => adminApi.audit(`limit=100${action ? `&action=${encodeURIComponent(action)}` : ""}`));

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <input
          value={action}
          onChange={(e) => setAction(e.target.value)}
          placeholder="Filter by action (e.g. user.suspend, facility.update, wallet.adjust)..."
          className={`${inputCls} max-w-md`}
        />
        <button onClick={() => void downloadAuditCsv().catch((e) => toast.error((e as Error).message))} className={btnGhostCls}>
          <Download className="h-3.5 w-3.5" />
          {t("exportAuditCsv")}
        </button>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-start text-xs font-medium text-muted-foreground">
              <th className="p-3.5 text-start">Action</th>
              <th className="p-3.5 text-start">Target</th>
              <th className="p-3.5 text-start">{t("reasonLbl")}</th>
              <th className="p-3.5 text-start">Actor ID</th>
              <th className="p-3.5 text-end">Timestamp</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {(data?.entries ?? []).map((e: any) => (
              <tr key={e.id} className="hover:bg-muted/20 transition-colors">
                <td className="p-3.5">
                  <Badge variant="purple">{e.action}</Badge>
                </td>
                <td className="p-3.5 text-xs">
                  <span className="font-medium text-foreground">{e.target_type}</span>
                  {e.target_id && <span className="ms-1 font-mono text-[10px] text-muted-foreground">({e.target_id.slice(0, 8)}…)</span>}
                </td>
                <td className="p-3.5 text-xs text-foreground">{e.reason || "—"}</td>
                <td className="p-3.5 font-mono text-[11px] text-muted-foreground">{e.actor_id.slice(0, 8)}…</td>
                <td className="p-3.5 text-end text-[11px] text-muted-foreground">{new Date(e.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {data && data.entries.length === 0 && (
          <div className="p-8 text-center text-xs text-muted-foreground">{t("noData")}</div>
        )}
      </Card>
    </div>
  );
}

/* =========================================================================
   12. DATABASE — LIVE TABLES (ADD / EDIT WHERE SAFE)
   ========================================================================= */
type DbField = { key: string; type: "text" | "number" | "bool" | "select" | "textarea" | "list" | "json"; options?: string[]; def?: string };
type DbTable = { name: string; pk: string; fields: DbField[]; creatable?: boolean };

const DB_TABLES: DbTable[] = [
  { name: "facilities", pk: "id", creatable: true, fields: [
    { key: "name", type: "text" }, { key: "name_ar", type: "text" }, { key: "city", type: "text", def: "Casablanca" },
    { key: "address", type: "text" }, { key: "lat", type: "number", def: "33.59" }, { key: "lng", type: "number", def: "-7.62" },
    { key: "price_per_hour_cents", type: "number", def: "1500" }, { key: "total_capacity", type: "number", def: "100" },
    { key: "authorized_capacity", type: "number", def: "50" }, { key: "available", type: "number", def: "50" },
    { key: "features", type: "list", def: "covered,cctv" }, { key: "open_24h", type: "bool", def: "true" }, { key: "active", type: "bool", def: "true" },
  ]},
  { name: "profiles", pk: "id", fields: [
    { key: "display_name", type: "text" }, { key: "phone", type: "text" }, { key: "vehicle_plate", type: "text" },
    { key: "vehicle_model", type: "text" }, { key: "status", type: "select", options: ["active", "suspended"] },
  ]},
  { name: "bookings", pk: "id", fields: [] },
  { name: "cameras", pk: "id", creatable: true, fields: [
    { key: "label", type: "text" }, { key: "facility_id", type: "text" },
    { key: "status", type: "select", options: ["active", "inactive"], def: "active" },
  ]},
  { name: "camera_events", pk: "id", fields: [] },
  { name: "incidents", pk: "id", creatable: true, fields: [
    { key: "kind", type: "select", options: ["user_report", "booking_complaint", "facility", "camera", "system", "ai_error"], def: "user_report" },
    { key: "title", type: "text" }, { key: "details", type: "textarea" },
    { key: "status", type: "select", options: ["open", "investigating", "resolved", "dismissed"], def: "open" },
  ]},
  { name: "wallets", pk: "user_id", fields: [] },
  { name: "wallet_transactions", pk: "id", fields: [] },
  { name: "user_roles", pk: "id", fields: [] },
  { name: "app_settings", pk: "key", creatable: true, fields: [
    { key: "key", type: "text" }, { key: "value", type: "json" },
  ]},
  { name: "audit_logs", pk: "id", fields: [] },
];

function dbCell(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "boolean") return v ? "✓" : "—";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  const s = String(v);
  return s.length > 42 ? `${s.slice(0, 42)}…` : s;
}

function DatabaseSection() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [tableName, setTableName] = useState("facilities");
  const [search, setSearch] = useState("");
  const [editor, setEditor] = useState<{ mode: "create" | "edit"; row: Record<string, unknown> } | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);

  const table = DB_TABLES.find((x) => x.name === tableName) ?? DB_TABLES[0];
  const { data, isLoading } = useSection(`database-${tableName}`, () => adminApi.databaseRows(tableName));
  const rows: Record<string, unknown>[] = data?.rows ?? [];
  const editable = table.fields.length > 0;
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return q ? rows.filter((r) => JSON.stringify(r).toLowerCase().includes(q)) : rows;
  }, [rows, search]);
  const columns = useMemo(() => {
    const keys: string[] = [];
    for (const r of filtered) for (const k of Object.keys(r)) if (!keys.includes(k)) keys.push(k);
    keys.sort((a, b) => (a === table.pk ? -1 : b === table.pk ? 1 : 0));
    return keys.slice(0, 8);
  }, [filtered, table.pk]);

  const openEditor = (mode: "create" | "edit", row: Record<string, unknown> = {}) => {
    const next: Record<string, string> = {};
    for (const f of table.fields) {
      if (mode === "create" && table.name === "app_settings" && f.key === "key") next[f.key] = "";
      else if (mode === "create") next[f.key] = f.def ?? "";
      else {
        const v = row[f.key];
        next[f.key] = f.type === "list" && Array.isArray(v) ? v.join(",") : f.type === "json" ? JSON.stringify(v ?? null) : v === null || v === undefined ? "" : String(v);
      }
    }
    if (mode === "edit" && table.name === "app_settings") delete next.key;
    setForm(next); setReason(""); setEditor({ mode, row });
  };

  const submit = async () => {
    if (!editor) return;
    if (editor.mode === "edit" && reason.trim().length < 3) { toast.error(t("reasonLbl")); return; }
    try {
      setSaving(true);
      const payload: Record<string, unknown> = {};
      for (const f of table.fields) {
        if (editor.mode === "edit" && table.name === "app_settings" && f.key === "key") continue;
        const raw = form[f.key] ?? "";
        if (f.type === "number") payload[f.key] = raw === "" ? null : Number(raw);
        else if (f.type === "bool") payload[f.key] = raw === "true";
        else if (f.type === "list") payload[f.key] = raw.split(",").map((s) => s.trim()).filter(Boolean);
        else if (f.type === "json") payload[f.key] = JSON.parse(raw || "null");
        else payload[f.key] = raw === "" ? null : raw;
      }
      if (table.name === "cameras" && !payload.facility_id) delete payload.facility_id;
      if (editor.mode === "create") await adminApi.createDatabaseRow(table.name, payload, reason.trim() || undefined);
      else await adminApi.updateDatabaseRow(table.name, String(editor.row[table.pk]), payload, reason.trim());
      toast.success(t("saved"));
      setEditor(null);
      void qc.invalidateQueries({ queryKey: ["admin"] });
    } catch (e) { toast.error((e as Error).message); } finally { setSaving(false); }
  };

  if (!metaBackendConfigured()) return <Card className="p-8 text-center text-muted-foreground">{t("backendOff")}</Card>;

  return (
    <div className="space-y-4">
      <p className="text-xs text-muted-foreground">{t("dbBrowse")}</p>
      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label={t("dbTable")}>
        {DB_TABLES.map((x) => (
          <button key={x.name} onClick={() => { setTableName(x.name); setSearch(""); }} className={x.name === tableName ? btnPrimaryCls : btnGhostCls}>
            {x.name}
          </button>
        ))}
      </div>

      <Card className="border-amber-300/60 bg-amber-50/60 p-3 text-[11px] text-amber-900 dark:border-amber-900/60 dark:bg-amber-950/20 dark:text-amber-200">
        {t("dbProtectedNote")}
      </Card>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative flex-1">
          <Search className="absolute start-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("dbSearchRows")} className={`${inputCls} ps-9`} />
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={editable ? "success" : "default"}>{editable ? t("dbEditable") : t("dbReadOnly")}</Badge>
          <span className="text-xs text-muted-foreground">{filtered.length} {t("dbRows")}</span>
          {table.creatable && (
            <button onClick={() => openEditor("create")} className={btnPrimaryCls}><Plus className="h-4 w-4" />{t("dbAddRow")}</button>
          )}
        </div>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr className="border-b border-border/60 bg-muted/30 text-xs font-medium text-muted-foreground">
              {columns.map((col) => <th key={col} className="p-3.5 text-start">{col}</th>)}
              {editable && <th className="p-3.5 text-end">{t("actionsLbl")}</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-border/60">
            {isLoading && <tr><td colSpan={columns.length + 1} className="p-6 text-center text-xs text-muted-foreground">{t("transcribing")}</td></tr>}
            {filtered.map((row, i) => (
              <tr key={String(row[table.pk] ?? i)} className="hover:bg-muted/20">
                {columns.map((col) => (
                  <td key={col} className={`p-3.5 text-xs ${col === table.pk ? "font-mono text-[11px]" : "text-foreground"}`}>{dbCell(row[col])}</td>
                ))}
                {editable && (
                  <td className="p-3.5 text-end">
                    <button onClick={() => openEditor("edit", row)} className={btnGhostCls}>{t("dbEditRow")}</button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && filtered.length === 0 && <div className="p-8 text-center text-xs text-muted-foreground">{t("noData")}</div>}
      </Card>

      {editor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-xs" role="dialog" aria-modal="true">
          <div className="max-h-[90vh] w-full max-w-xl overflow-y-auto rounded-2xl border border-border bg-card p-6 shadow-2xl">
            <div className="flex items-center justify-between border-b pb-3">
              <h3 className="font-display text-base font-semibold text-foreground">
                {editor.mode === "create" ? t("dbAddRow") : t("dbEditRow")} · {table.name}
              </h3>
              <button onClick={() => setEditor(null)} className="rounded-lg p-1 text-muted-foreground hover:bg-muted"><X className="h-5 w-5" /></button>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
              {table.fields.filter((f) => !(editor.mode === "edit" && table.name === "app_settings" && f.key === "key")).map((f) => (
                <div key={f.key} className={f.type === "textarea" || f.type === "json" ? "col-span-2" : ""}>
                  <label className="block text-muted-foreground">{f.key}</label>
                  {f.type === "bool" || f.type === "select" ? (
                    <select value={form[f.key] ?? ""} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} className={inputCls}>
                      {(f.type === "bool" ? ["true", "false"] : f.options ?? []).map((o) => <option key={o} value={o}>{o}</option>)}
                    </select>
                  ) : f.type === "textarea" || f.type === "json" ? (
                    <textarea rows={3} value={form[f.key] ?? ""} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} className="w-full rounded-xl border border-border bg-background p-2.5 text-xs text-foreground outline-none" />
                  ) : (
                    <input type={f.type === "number" ? "number" : "text"} step="any" value={form[f.key] ?? ""} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} className={inputCls} />
                  )}
                </div>
              ))}
              <div className="col-span-2">
                <label className="block text-muted-foreground">{t("reasonLbl")} {editor.mode === "edit" && <span className="text-destructive">*</span>}</label>
                <input value={reason} onChange={(e) => setReason(e.target.value)} className={inputCls} />
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2 border-t pt-4">
              <button onClick={() => setEditor(null)} className={btnGhostCls}>{t("cancel")}</button>
              <button onClick={() => void submit()} disabled={saving} className={btnPrimaryCls}>{t("dbSaveRow")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================================================================
   13. SYSTEM SETTINGS
   ========================================================================= */
function SettingsSection({ confirm }: { confirm: (s: ConfirmState) => void }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const { data } = useSection("settings", adminApi.settings);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const current: Record<string, unknown> = data?.settings ?? {};

  const field = (key: string, label: string, type = "text", help?: string) => (
    <div className="space-y-1">
      <label className="text-xs font-medium text-foreground">{label}</label>
      <input
        type={type}
        className={inputCls}
        value={draft[key] ?? String(current[key] ?? "")}
        onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
      />
      {help && <p className="text-[11px] text-muted-foreground">{help}</p>}
    </div>
  );

  return (
    <div className="space-y-4">
      <Card className="space-y-5">
        <div>
          <p className="font-semibold text-foreground">Application & Operational Boundaries</p>
          <p className="text-xs text-muted-foreground">Server-side validated settings. Environment secrets are strictly protected and never modified here.</p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {field("app_name", "Application Name", "text", "Public branding name")}
          {field("nearby_default_radius_km", "Nearby Parking Search Radius (km)", "number", "Search perimeter for geolocation queries")}
          {field("hold_expiry_minutes", "Hold Expiry Window (minutes)", "number", "Temporary hold release timeout")}
          {field("cancellation_window_hours", "Full-Refund Cancellation Window (hours)", "number", "Hours before booking start time for 100% refund")}
          {field("pricing_min_cents", "Minimum Allowed Hourly Price (cents)", "number", "Global lower price boundary")}
          {field("pricing_max_cents", "Maximum Allowed Hourly Price (cents)", "number", "Global upper price boundary")}
        </div>

        <div className="flex justify-end border-t pt-4">
          <button
            className={btnPrimaryCls}
            onClick={() => confirm({
              title: t("saveSettings"),
              description: "System parameters will be updated in app_settings table and audited.",
              run: async (r) => {
                const parsed: Record<string, unknown> = {};
                for (const [k, v] of Object.entries(draft)) {
                  parsed[k] = k === "app_name" ? v : Number(v);
                }
                await adminApi.updateSettings(parsed, r);
                qc.invalidateQueries({ queryKey: ["admin"] });
              },
            })}
          >
            {t("saveSettings")}
          </button>
        </div>
      </Card>
    </div>
  );
}

/* =========================================================================
   ROOT ADMIN PAGE & SHELL
   ========================================================================= */
function AdminPage() {
  const { t, lang, setLang } = useI18n();
  const { user, roles, loading } = useAuth();
  const [section, setSection] = useState<SectionId>("overview");
  const [confirmState, setConfirmState] = useState<ConfirmState>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const confirm = (s: ConfirmState) => setConfirmState(s);

  if (loading) {
    return <div className="flex h-screen items-center justify-center text-sm text-muted-foreground">Loading control center...</div>;
  }

  if (!user) {
    return <div className="mx-auto max-w-md p-6"><SignInGate /></div>;
  }

  if (!roles.includes("admin")) {
    return (
      <div className="mx-auto max-w-md p-6">
        <Card className="text-center">
          <ShieldAlert className="mx-auto h-8 w-8 text-destructive" />
          <h2 className="mt-2 font-display text-lg font-semibold">{t("adminRestricted")}</h2>
          <p className="mt-1 text-xs text-muted-foreground">This control center is strictly for authorized ParkSpot administrators.</p>
          <Link to="/home" className="mt-4 inline-block text-xs font-semibold text-primary hover:underline">{t("home")}</Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#FBFBFA] text-foreground dark:bg-background">
      <div className="mx-auto flex max-w-[1500px]">
        {/* Desktop Sidebar */}
        <aside className="sticky top-0 hidden h-screen w-72 shrink-0 flex-col justify-between border-e border-border/80 bg-card p-4 lg:flex">
          <div>
            <div className="flex items-center gap-2.5 px-3 py-2">
              <img src={logo} alt="ParkSpot AI" className="h-8 w-8 object-contain" />
              <div>
                <p className="font-display text-sm font-bold tracking-tight text-foreground">ParkSpot AI</p>
                <div className="flex items-center gap-1.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  <p className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400">Control Center</p>
                </div>
              </div>
            </div>

            <nav className="mt-6 space-y-1">
              {SECTIONS.map((s) => {
                const active = section === s.id;
                return (
                  <button
                    key={s.id}
                    onClick={() => setSection(s.id)}
                    className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-xs font-medium transition-all ${
                      active
                        ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                        : "text-muted-foreground hover:bg-muted/70 hover:text-foreground"
                    }`}
                  >
                    <s.icon className={`h-4 w-4 shrink-0 ${active ? "text-primary-foreground" : "text-muted-foreground"}`} />
                    <span>{t(s.key)}</span>
                  </button>
                );
              })}
            </nav>
          </div>

          <div className="border-t border-border/60 pt-4">
            <div className="flex items-center justify-between px-3 pb-2 text-xs">
              <span className="text-muted-foreground">{t("language")}</span>
              <button
                onClick={() => setLang(lang === "en" ? "ar" : "en")}
                className="flex items-center gap-1 rounded-lg border border-border px-2 py-1 font-semibold text-foreground hover:bg-muted"
              >
                <Globe className="h-3 w-3" />
                {lang === "en" ? "العربية" : "English"}
              </button>
            </div>
            <div className="rounded-xl bg-muted/40 p-2.5">
              <p className="truncate text-xs font-semibold text-foreground">{user.email}</p>
              <Badge variant="purple">Super Admin</Badge>
            </div>
            <button
              onClick={() => void supabase.auth.signOut()}
              className="mt-2 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-destructive transition hover:bg-destructive/10"
            >
              <LogOut className="h-4 w-4" />
              {t("logout")}
            </button>
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">
          {/* Top Mobile Bar */}
          <div className="mb-4 flex items-center justify-between lg:hidden">
            <div className="flex items-center gap-2">
              <img src={logo} alt="ParkSpot AI" className="h-7 w-7 object-contain" />
              <p className="font-display font-bold text-foreground">ParkSpot Admin</p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setLang(lang === "en" ? "ar" : "en")}
                className="rounded-lg border p-1.5 text-xs text-foreground"
              >
                {lang === "en" ? "عربي" : "EN"}
              </button>
              <button onClick={() => void supabase.auth.signOut()} className="text-destructive">
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Horizontal section navigation pills on mobile */}
          <nav className="no-scrollbar mb-5 flex gap-2 overflow-x-auto pb-1 lg:hidden">
            {SECTIONS.map((s) => (
              <button
                key={s.id}
                onClick={() => setSection(s.id)}
                className={`flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
                  section === s.id
                    ? "border-primary bg-primary text-primary-foreground font-semibold"
                    : "border-border/80 bg-card text-foreground"
                }`}
              >
                <s.icon className="h-3.5 w-3.5" />
                {t(s.key)}
              </button>
            ))}
          </nav>

          {/* Section Title */}
          <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
            <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
              {t(SECTIONS.find((s) => s.id === section)!.key)}
            </h1>
            <p className="text-xs text-muted-foreground">ParkSpot AI Super Administrator Control Surface</p>
          </div>

          {/* Section Content */}
          {section === "overview" && <Overview confirm={confirm} onNavigate={setSection} />}
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
          {section === "database" && <DatabaseSection />}
          {section === "settings" && <SettingsSection confirm={confirm} />}
        </main>
      </div>

      <ConfirmModal state={confirmState} close={() => setConfirmState(null)} />
    </div>
  );
}
