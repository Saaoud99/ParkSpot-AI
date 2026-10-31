import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import garage from "@/assets/garage.jpg";
import underground from "@/assets/underground.jpg";
import openlot from "@/assets/openlot.jpg";
import rooftop from "@/assets/rooftop.jpg";

export const facilityImages: Record<string, string> = { garage, underground, openlot, rooftop };
export const imageFor = (key: string) => facilityImages[key] ?? garage;

/** Format integer cents as MAD, e.g. 1500 -> "15.00 MAD". */
export function mad(cents: number | bigint, lang: "en" | "ar" = "en") {
  const v = (Number(cents) / 100).toFixed(2);
  return lang === "ar" ? `${v} درهم` : `${v} MAD`;
}

export function useFacilities() {
  return useQuery({
    queryKey: ["facilities"],
    queryFn: async () => {
      const { data, error } = await supabase.from("facilities").select("*").order("rating", { ascending: false });
      if (error) throw error;
      // Deactivated facilities (admin toggle, migration 0001) are not
      // bookable inventory — never show them to drivers. Rows from a
      // pre-0001 database have no `active` column and pass through.
      return data.filter((f) => (f as { active?: boolean }).active !== false);
    },
  });
}

export function useWallet(userId?: string) {
  return useQuery({
    queryKey: ["wallet", userId],
    enabled: !!userId,
    queryFn: async () => {
      const { data, error } = await supabase.from("wallets").select("*").eq("user_id", userId!).maybeSingle();
      if (error) throw error;
      return data;
    },
  });
}

export function useTransactions(userId?: string, limit = 100) {
  return useQuery({
    queryKey: ["tx", userId, limit],
    enabled: !!userId,
    queryFn: async () => {
      const { data, error } = await supabase.from("wallet_transactions").select("*")
        .eq("user_id", userId!).order("created_at", { ascending: false }).limit(limit);
      if (error) throw error;
      return data;
    },
  });
}

/** Map a database error into a friendly code. */
export function errCode(e: unknown): { code: string; shortfall?: number } {
  const msg = (e as { message?: string })?.message ?? String(e);
  const m = msg.match(/INSUFFICIENT_FUNDS:(\d+)/);
  if (m) return { code: "INSUFFICIENT_FUNDS", shortfall: Number(m[1]) };
  const k = msg.match(/[A-Z_]{5,}/);
  return { code: k?.[0] ?? msg };
}
