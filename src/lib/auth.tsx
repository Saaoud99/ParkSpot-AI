import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import type { User } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

type Ctx = { user: User | null; loading: boolean; roles: string[] };
const AuthCtx = createContext<Ctx>({ user: null, loading: true, roles: [] });

/** i18n keys for the auth errors users actually hit, so raw API messages never reach the UI. */
export type AuthErrorKey = "invalidCredentials" | "accountExists";

export function authErrorKey(err: unknown): AuthErrorKey | null {
  const e = err as { code?: string; message?: string } | null;
  const code = e?.code ?? "";
  const msg = (e?.message ?? "").toLowerCase();
  if (code === "invalid_credentials" || msg.includes("invalid login credentials")) return "invalidCredentials";
  if (code === "user_already_exists" || msg.includes("already registered") || msg.includes("already been registered")) return "accountExists";
  return null;
}

/**
 * Signing up with an already-registered email returns a fake "success" user
 * with no identities (Supabase hides account existence). Detect it so we can
 * say "sign in instead" rather than silently creating a duplicate flow.
 */
export function isExistingAccount(user: User | null | undefined): boolean {
  return !!user && Array.isArray(user.identities) && user.identities.length === 0;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const qc = useQueryClient();
  const rolesFor = useRef<string | null>(null);

  useEffect(() => {
    let alive = true;

    const loadRoles = (u: User | null) => {
      if (!u) { rolesFor.current = null; setRoles([]); return; }
      if (rolesFor.current === u.id) return;
      rolesFor.current = u.id;
      // Deferred: awaiting Supabase calls inside onAuthStateChange can deadlock
      // on the auth lock, so role loading runs after the callback returns.
      setTimeout(() => {
        if (!alive) return;
        void supabase.from("user_roles").select("role").eq("user_id", u.id)
          .then(({ data }) => { if (alive && rolesFor.current === u.id) setRoles((data ?? []).map((r) => r.role)); });
      }, 0);
    };

    // onAuthStateChange fires INITIAL_SESSION with the stored session. It is
    // the single source of truth — no separate getUser() call that can
    // resolve late and wipe a fresh sign-in.
    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      if (!alive) return;
      const u = session?.user ?? null;
      setUser(u);
      setLoading(false);
      if (event === "SIGNED_OUT") { loadRoles(null); qc.clear(); return; }
      loadRoles(u);
      if (event === "SIGNED_IN" || event === "USER_UPDATED") qc.invalidateQueries();
    });

    // Fallback: if INITIAL_SESSION somehow never arrives, stop loading instead
    // of leaving gated pages blank forever. INITIAL_SESSION sets the user.
    void supabase.auth.getSession()
      .then(() => { if (alive) setLoading(false); })
      .catch(() => { if (alive) setLoading(false); });

    return () => { alive = false; sub.subscription.unsubscribe(); };
  }, [qc]);

  return <AuthCtx.Provider value={{ user, loading, roles }}>{children}</AuthCtx.Provider>;
}
export const useAuth = () => useContext(AuthCtx);
