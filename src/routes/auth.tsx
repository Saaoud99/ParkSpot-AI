import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { Phone } from "@/components/AppShell";
import { supabase } from "@/integrations/supabase/client";
import { lovable } from "@/integrations/lovable/index";
import { useI18n } from "@/lib/i18n";
import logo from "@/assets/logo.png";
import garage from "@/assets/garage.jpg";

export const Route = createFileRoute("/auth")({
  head: () => ({ meta: [{ title: "Sign in — ParkSpot AI" }, { name: "description", content: "Sign in or create your ParkSpot AI account." }, { property: "og:title", content: "Sign in — ParkSpot AI" }, { property: "og:description", content: "Access your wallet and bookings." }] }),
  component: AuthPage,
});

function AuthPage() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (mode === "up") {
        const { data, error } = await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin + "/home", data: { full_name: name } } });
        if (error) throw error;
        if (!data.session) { toast.success(t("checkEmail")); setMode("in"); return; }
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
      }
      nav({ to: "/home" });
    } catch (err) {
      toast.error((err as Error).message);
    } finally { setBusy(false); }
  };

  const google = async () => {
    const r = await lovable.auth.signInWithOAuth("google", { redirect_uri: window.location.origin });
    if (r.error) { toast.error(String(r.error.message ?? r.error)); return; }
    if (r.redirected) return;
    nav({ to: "/home" });
  };

  const input = "h-12 w-full rounded-2xl border bg-card px-4 text-sm outline-none focus:border-primary";
  return (
    <Phone>
      <div className="relative h-56">
        <img src={garage} alt="" className="h-full w-full object-cover" />
        <div className="absolute inset-0 bg-fade" />
      </div>
      <div className="-mt-12 flex-1 rounded-t-[2rem] bg-background px-6 pb-8 pt-6">
        <img src={logo} alt="ParkSpot AI" width={48} height={48} className="h-12 w-12 object-contain" />
        <h1 className="mt-3 font-display text-3xl font-semibold">{mode === "in" ? t("signIn") : t("signUp")}</h1>
        <p className="text-sm text-muted-foreground">{t("tagline")}</p>
        <button onClick={google} className="mt-6 flex h-12 w-full items-center justify-center gap-2 rounded-full border bg-card font-semibold">
          <span className="text-lg font-bold text-primary">G</span>{t("continueGoogle")}
        </button>
        <div className="my-5 flex items-center gap-3 text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />{t("or")}<span className="h-px flex-1 bg-border" /></div>
        <form onSubmit={submit} className="space-y-3">
          {mode === "up" && <input className={input} placeholder={t("name")} value={name} onChange={(e) => setName(e.target.value)} required />}
          <input className={input} type="email" placeholder={t("email")} value={email} onChange={(e) => setEmail(e.target.value)} required />
          <input className={input} type="password" minLength={6} placeholder={t("password")} value={password} onChange={(e) => setPassword(e.target.value)} required />
          <button disabled={busy} className="h-12 w-full rounded-full bg-primary font-semibold text-primary-foreground shadow-lift disabled:opacity-60">{mode === "in" ? t("signIn") : t("signUp")}</button>
        </form>
        <button onClick={() => setMode(mode === "in" ? "up" : "in")} className="mt-5 w-full text-center text-sm text-muted-foreground">
          {mode === "in" ? t("noAccount") : t("haveAccount")} <span className="font-semibold text-primary">{mode === "in" ? t("signUp") : t("signIn")}</span>
        </button>
        <button onClick={() => nav({ to: "/home" })} className="mt-3 w-full text-center text-sm text-muted-foreground underline">{t("explore")}</button>
      </div>
    </Phone>
  );
}
