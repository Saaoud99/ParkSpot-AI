import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { User } from "@supabase/supabase-js";
import { useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";

type Ctx = { user: User | null; loading: boolean; roles: string[] };
const AuthCtx = createContext<Ctx>({ user: null, loading: true, roles: [] });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [roles, setRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const qc = useQueryClient();

  useEffect(() => {
    const loadRoles = async (u: User | null) => {
      if (!u) return setRoles([]);
      const { data } = await supabase.from("user_roles").select("role").eq("user_id", u.id);
      setRoles((data ?? []).map((r) => r.role));
    };
    const { data: sub } = supabase.auth.onAuthStateChange((event, session) => {
      setUser(session?.user ?? null);
      if (event === "SIGNED_IN" || event === "SIGNED_OUT" || event === "USER_UPDATED") {
        void loadRoles(session?.user ?? null);
        if (event === "SIGNED_OUT") qc.clear(); else qc.invalidateQueries();
      }
    });
    supabase.auth.getUser().then(({ data }) => {
      setUser(data.user ?? null);
      void loadRoles(data.user ?? null);
      setLoading(false);
    });
    return () => sub.subscription.unsubscribe();
  }, [qc]);

  return <AuthCtx.Provider value={{ user, loading, roles }}>{children}</AuthCtx.Provider>;
}
export const useAuth = () => useContext(AuthCtx);
