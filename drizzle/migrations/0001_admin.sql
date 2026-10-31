-- 0001_admin.sql — Super Admin Control Center support.
-- Apply manually in the Supabase SQL editor (Dashboard → SQL Editor).
-- Everything is additive and follows the existing has_role() RLS pattern.
-- All wallet money movement stays inside SECURITY DEFINER functions.

-- ── profiles: suspension flag ───────────────────────────────────────────────
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'active'
  CHECK (status IN ('active','suspended'));

-- ── facilities: total vs authorized capacity + activation ───────────────────
ALTER TABLE public.facilities ADD COLUMN IF NOT EXISTS total_capacity integer;
ALTER TABLE public.facilities ADD COLUMN IF NOT EXISTS authorized_capacity integer;
ALTER TABLE public.facilities ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true;
UPDATE public.facilities
  SET total_capacity = capacity, authorized_capacity = capacity
  WHERE total_capacity IS NULL;
ALTER TABLE public.facilities ALTER COLUMN total_capacity SET NOT NULL;
ALTER TABLE public.facilities ALTER COLUMN authorized_capacity SET NOT NULL;
-- invariant: authorized can never exceed physical capacity
ALTER TABLE public.facilities
  ADD CONSTRAINT facilities_authorized_le_total
  CHECK (authorized_capacity <= total_capacity AND authorized_capacity >= 0 AND total_capacity >= 0);
GRANT INSERT ON public.facilities TO authenticated;
CREATE POLICY "admin insert facilities" ON public.facilities FOR INSERT TO authenticated
  WITH CHECK (public.has_role(auth.uid(),'admin'));

-- ── wallet transaction type: admin adjustments ──────────────────────────────
DO $$ BEGIN
  ALTER TABLE public.wallet_transactions DROP CONSTRAINT IF EXISTS wallet_transactions_type_check;
  ALTER TABLE public.wallet_transactions
    ADD CONSTRAINT wallet_transactions_type_check
    CHECK (type IN ('topup','booking_charge','refund','adjustment'));
END $$;

-- ── admin read/write policies (admin role only; drivers/partners unaffected) ─
CREATE POLICY "admin read profiles" ON public.profiles FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(),'admin'));
CREATE POLICY "admin update profiles" ON public.profiles FOR UPDATE TO authenticated
  USING (public.has_role(auth.uid(),'admin')) WITH CHECK (public.has_role(auth.uid(),'admin'));
CREATE POLICY "admin read roles" ON public.user_roles FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(),'admin'));
GRANT INSERT, DELETE ON public.user_roles TO authenticated;
CREATE POLICY "admin grant roles" ON public.user_roles FOR INSERT TO authenticated
  WITH CHECK (public.has_role(auth.uid(),'admin'));
CREATE POLICY "admin revoke roles" ON public.user_roles FOR DELETE TO authenticated
  USING (public.has_role(auth.uid(),'admin'));
CREATE POLICY "admin read wallets" ON public.wallets FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(),'admin'));
CREATE POLICY "admin read tx" ON public.wallet_transactions FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(),'admin'));

-- ── audit log (append-only for authenticated users) ─────────────────────────
CREATE TABLE public.audit_logs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  actor_id uuid NOT NULL,
  action text NOT NULL,
  target_type text NOT NULL,
  target_id text,
  reason text,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT ON public.audit_logs TO authenticated;
GRANT ALL ON public.audit_logs TO service_role;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin read audit" ON public.audit_logs FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(),'admin'));
CREATE POLICY "admin write audit" ON public.audit_logs FOR INSERT TO authenticated
  WITH CHECK (public.has_role(auth.uid(),'admin') AND actor_id = auth.uid());
-- deliberately NO update/delete policies: the log is append-only via the API

-- ── cameras & access events ─────────────────────────────────────────────────
CREATE TABLE public.cameras (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  facility_id uuid REFERENCES public.facilities(id),
  label text NOT NULL,
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
  last_event_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON public.cameras TO authenticated;
GRANT ALL ON public.cameras TO service_role;
ALTER TABLE public.cameras ENABLE ROW LEVEL SECURITY;
CREATE POLICY "ops read cameras" ON public.cameras FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(),'admin') OR public.has_role(auth.uid(),'partner'));
CREATE POLICY "admin write cameras" ON public.cameras FOR INSERT TO authenticated
  WITH CHECK (public.has_role(auth.uid(),'admin'));
CREATE POLICY "admin update cameras" ON public.cameras FOR UPDATE TO authenticated
  USING (public.has_role(auth.uid(),'admin')) WITH CHECK (public.has_role(auth.uid(),'admin'));

CREATE TABLE public.camera_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  camera_id uuid REFERENCES public.cameras(id),
  facility_id uuid REFERENCES public.facilities(id),
  kind text NOT NULL,
  ocr_confidence numeric,
  access_result text,
  simulated boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT ON public.camera_events TO authenticated;
GRANT ALL ON public.camera_events TO service_role;
ALTER TABLE public.camera_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY "ops read camera events" ON public.camera_events FOR SELECT TO authenticated
  USING (public.has_role(auth.uid(),'admin') OR public.has_role(auth.uid(),'partner'));
CREATE POLICY "ops write camera events" ON public.camera_events FOR INSERT TO authenticated
  WITH CHECK (public.has_role(auth.uid(),'admin') OR public.has_role(auth.uid(),'partner'));

-- ── incidents / reports ─────────────────────────────────────────────────────
CREATE TABLE public.incidents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind text NOT NULL CHECK (kind IN ('user_report','booking_complaint','facility','camera','system','ai_error')),
  title text NOT NULL,
  details text,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','investigating','resolved','dismissed')),
  reporter_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON public.incidents TO authenticated;
GRANT ALL ON public.incidents TO service_role;
ALTER TABLE public.incidents ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin manage incidents" ON public.incidents FOR ALL TO authenticated
  USING (public.has_role(auth.uid(),'admin')) WITH CHECK (public.has_role(auth.uid(),'admin'));
CREATE POLICY "users report incidents" ON public.incidents FOR INSERT TO authenticated
  WITH CHECK (reporter_id = auth.uid());

-- ── application settings (allow-listed keys, validated by the backend) ──────
CREATE TABLE public.app_settings (
  key text PRIMARY KEY,
  value jsonb NOT NULL,
  updated_by uuid,
  updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE ON public.app_settings TO authenticated;
GRANT ALL ON public.app_settings TO service_role;
ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "admin manage settings" ON public.app_settings FOR ALL TO authenticated
  USING (public.has_role(auth.uid(),'admin')) WITH CHECK (public.has_role(auth.uid(),'admin'));

-- ── admin booking cancellation (same refund policy as cancel_booking) ───────
CREATE OR REPLACE FUNCTION public.admin_cancel_booking(p_booking_id uuid, p_reason text)
RETURNS public.bookings LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE actor uuid := auth.uid(); b public.bookings; refund bigint;
BEGIN
  IF actor IS NULL OR NOT public.has_role(actor,'admin') THEN RAISE EXCEPTION 'FORBIDDEN'; END IF;
  IF p_reason IS NULL OR length(trim(p_reason)) < 3 THEN RAISE EXCEPTION 'REASON_REQUIRED'; END IF;
  SELECT * INTO b FROM public.bookings WHERE id = p_booking_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'BOOKING_NOT_FOUND'; END IF;
  IF b.status <> 'confirmed' THEN RETURN b; END IF;
  PERFORM 1 FROM public.wallets WHERE user_id = b.user_id FOR UPDATE;
  IF now() <= b.start_at - interval '2 hours' THEN refund := b.total_cents;
  ELSIF now() < b.start_at THEN refund := b.total_cents / 2;
  ELSE refund := 0; END IF;
  UPDATE public.bookings SET status = 'cancelled', refunded_cents = refund WHERE id = b.id RETURNING * INTO b;
  UPDATE public.facilities SET available = LEAST(authorized_capacity, available + 1) WHERE id = b.facility_id;
  IF refund > 0 THEN
    UPDATE public.wallets SET available_cents = available_cents + refund, updated_at = now() WHERE user_id = b.user_id;
    INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,booking_id,description,idempotency_key)
      VALUES (b.user_id,'refund',refund,'succeeded',b.id,'Admin cancellation refund','refund-' || b.id);
  END IF;
  INSERT INTO public.audit_logs(actor_id,action,target_type,target_id,reason,metadata)
    VALUES (actor,'booking.cancel','booking',b.id::text,p_reason,jsonb_build_object('refund_cents',refund,'user_id',b.user_id));
  RETURN b;
END $$;

-- ── admin wallet adjustment (reason required, never negative, audited) ──────
CREATE OR REPLACE FUNCTION public.admin_adjust_wallet(p_user_id uuid, p_amount_cents bigint, p_reason text)
RETURNS public.wallet_transactions LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE actor uuid := auth.uid(); w public.wallets; tx public.wallet_transactions;
BEGIN
  IF actor IS NULL OR NOT public.has_role(actor,'admin') THEN RAISE EXCEPTION 'FORBIDDEN'; END IF;
  IF p_reason IS NULL OR length(trim(p_reason)) < 3 THEN RAISE EXCEPTION 'REASON_REQUIRED'; END IF;
  IF p_amount_cents = 0 OR abs(p_amount_cents) > 100000000 THEN RAISE EXCEPTION 'INVALID_AMOUNT'; END IF;
  SELECT * INTO w FROM public.wallets WHERE user_id = p_user_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'NO_WALLET'; END IF;
  IF w.available_cents + p_amount_cents < 0 THEN RAISE EXCEPTION 'INSUFFICIENT_FUNDS'; END IF;
  UPDATE public.wallets SET available_cents = available_cents + p_amount_cents, updated_at = now()
    WHERE user_id = p_user_id;
  INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,description,idempotency_key)
    VALUES (p_user_id,'adjustment',p_amount_cents,'succeeded','Admin adjustment: ' || p_reason,'adj-' || gen_random_uuid()::text)
    RETURNING * INTO tx;
  INSERT INTO public.audit_logs(actor_id,action,target_type,target_id,reason,metadata)
    VALUES (actor,'wallet.adjust','wallet',p_user_id::text,p_reason,jsonb_build_object('amount_cents',p_amount_cents,'tx_id',tx.id));
  RETURN tx;
END $$;

REVOKE EXECUTE ON FUNCTION public.admin_cancel_booking(uuid,text), public.admin_adjust_wallet(uuid,bigint,text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_cancel_booking(uuid,text), public.admin_adjust_wallet(uuid,bigint,text) TO authenticated;
