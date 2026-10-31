import type { ReactNode } from "react";
import { Link, useLocation } from "@tanstack/react-router";
import { Home, Map, CalendarCheck, Wallet, User, Sparkles } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import logo from "@/assets/logo.png";

export function Phone({ children }: { children: ReactNode }) {
  const { dir } = useI18n();
  return (
    <div dir={dir} className="min-h-screen bg-muted md:py-8">
      <div className="relative mx-auto flex min-h-screen w-full max-w-[440px] flex-col overflow-hidden bg-background md:min-h-[860px] md:rounded-[2.5rem] md:border md:shadow-lift">
        {children}
      </div>
    </div>
  );
}

const tabs = [
  { to: "/home", icon: Home, key: "home" },
  { to: "/map", icon: Map, key: "map" },
  { to: "/assistant", icon: Sparkles, key: "assistant" },
  { to: "/bookings", icon: CalendarCheck, key: "bookings" },
  { to: "/wallet", icon: Wallet, key: "wallet" },
  { to: "/profile", icon: User, key: "profile" },
] as const;

export function AppShell({ children, title, back }: { children: ReactNode; title?: string; back?: boolean }) {
  const { t } = useI18n();
  const loc = useLocation();
  return (
    <Phone>
      <header className="sticky top-0 z-20 flex items-center gap-3 border-b bg-background/90 px-5 py-3 backdrop-blur">
        {back ? (
          <button onClick={() => history.back()} className="rounded-full border px-3 py-1 text-sm text-muted-foreground rtl:rotate-0">
            <span className="inline-block rtl:rotate-180">←</span>
          </button>
        ) : (
          <img src={logo} alt="ParkSpot AI" width={32} height={32} className="h-8 w-8 object-contain" />
        )}
        <div className="flex-1 truncate font-display text-lg font-semibold">{title ?? "ParkSpot AI"}</div>
      </header>
      <main className="flex-1 overflow-y-auto pb-28">{children}</main>
      <nav className="absolute inset-x-0 bottom-0 z-30 border-t bg-card/95 px-2 pb-3 pt-2 backdrop-blur">
        <ul className="grid grid-cols-6">
          {tabs.map(({ to, icon: Icon, key }) => {
            const active = loc.pathname.startsWith(to);
            return (
              <li key={to}>
                <Link to={to} className={cn("flex flex-col items-center gap-1 rounded-xl py-1.5 text-[10px] font-medium transition-colors",
                  active ? "text-primary" : "text-muted-foreground")}>
                  <span className={cn("rounded-full px-3 py-1", active && "bg-secondary")}><Icon className="h-5 w-5" /></span>
                  {t(key)}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </Phone>
  );
}

export function SignInGate() {
  const { t } = useI18n();
  return (
    <div className="m-5 rounded-3xl border bg-card p-6 text-center shadow-soft">
      <img src={logo} alt="" width={56} height={56} className="mx-auto h-14 w-14 object-contain" />
      <h2 className="mt-3 font-display text-xl font-semibold">{t("signInToContinue")}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("signInBody")}</p>
      <Link to="/auth" className="mt-5 inline-flex h-11 items-center rounded-full bg-primary px-6 text-sm font-semibold text-primary-foreground">
        {t("signIn")}
      </Link>
    </div>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("rounded-3xl border bg-card p-4 shadow-soft", className)}>{children}</div>;
}
