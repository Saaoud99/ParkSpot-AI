-- 0003_authorized_availability.sql — authorized-capacity ceiling enforced by
-- a confirmed-booking count, consistent facility-row locking, and a
-- capacity-change clamp trigger. (Phase 4, Option A.)
-- Apply AFTER 0000_migration.sql, 0001_admin.sql and
-- 0002_booking_capacity_guard.sql, in the Supabase SQL editor.
--
-- Business semantics (Option A, explicitly accepted):
--   * `facilities.available` is a live operational free-space correction
--     owned by Ops — NOT a persistent physical-closure ceiling.
--   * A cancellation automatically returns ONE space to sale. Repeated
--     cancellations can therefore gradually erode a manually reduced
--     `available` figure; Ops re-applies the reduced figure when needed.
--   * What this migration guarantees regardless of the counter value:
--     total confirmed bookings for a facility can never exceed its
--     authorized capacity (authorized_capacity, falling back to the
--     legacy `capacity` column on pre-0001 rows).
--
-- Safety properties:
--   * The one-time repair at the end only ever LOWERS inflated counters
--     (LEAST). It never raises availability, so intentional manual
--     reductions (values below the computed remainder) are preserved.
--   * No table schema changes, no RLS policy changes, no permission
--     changes for partners. Function signatures and grants are preserved
--     (re-asserted below exactly as in 0001/0002).
--   * Wallet, refund, idempotency and authorization logic inside the
--     three booking functions is copied unchanged from 0002/0001.
--
-- Lock order (deadlock-free, transaction-atomic):
--   * create_booking:   wallet FOR UPDATE -> facility FOR UPDATE -> count.
--   * cancel paths:     booking FOR UPDATE -> wallet FOR UPDATE
--                       -> facility FOR UPDATE -> status flip -> count.
--   No path holding the facility lock ever waits on a wallet/booking row,
--   and the only booking-insert path (create_booking) holds the facility
--   lock, so the confirmed count read under that lock is exact.
--
-- Rollback: re-apply the create_booking/cancel_booking definitions from
-- 0002 and admin_cancel_booking from 0001, then
--   DROP TRIGGER IF EXISTS facilities_clamp_available_on_capacity
--     ON public.facilities;
--   DROP FUNCTION IF EXISTS public.clamp_available_to_authorized();

-- Supports the confirmed-booking counts below (additive, no data change).
CREATE INDEX IF NOT EXISTS bookings_facility_status_idx
  ON public.bookings (facility_id, status);

-- ── create_booking: + confirmed-count ceiling inside the facility lock ─────
CREATE OR REPLACE FUNCTION public.create_booking(p_facility_id uuid, p_start_at timestamptz, p_hours integer, p_idempotency_key text)
RETURNS public.bookings LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE uid uuid := auth.uid(); f public.facilities; w public.wallets; b public.bookings; total bigint; authorized integer; v_confirmed bigint; v_remaining integer;
BEGIN
  IF uid IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  IF p_hours < 1 OR p_hours > 24 THEN RAISE EXCEPTION 'INVALID_HOURS'; END IF;
  IF p_start_at < now() - interval '15 minutes' THEN RAISE EXCEPTION 'START_IN_PAST'; END IF;
  SELECT * INTO b FROM public.bookings WHERE idempotency_key = p_idempotency_key AND user_id = uid;
  IF FOUND THEN RETURN b; END IF;
  SELECT * INTO w FROM public.wallets WHERE user_id = uid FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'NO_WALLET'; END IF;
  SELECT * INTO f FROM public.facilities WHERE id = p_facility_id FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'FACILITY_NOT_FOUND'; END IF;
  IF NOT COALESCE(f.active, true) THEN RAISE EXCEPTION 'FACILITY_INACTIVE'; END IF;
  authorized := COALESCE(f.authorized_capacity, f.capacity);
  -- Authorized remaining from the actual confirmed-booking count, read
  -- while holding the facility row lock (cancellations take the same lock
  -- before changing any status, so this count cannot race them).
  SELECT COUNT(*) INTO v_confirmed FROM public.bookings
    WHERE facility_id = f.id AND status = 'confirmed';
  v_remaining := GREATEST(0, authorized - v_confirmed::integer);
  -- Sellable spaces are the lower of the Ops-corrected counter and the
  -- authorized remaining — the counter alone can no longer oversell.
  IF LEAST(f.available, v_remaining) < 1 THEN RAISE EXCEPTION 'FACILITY_FULL'; END IF;
  total := f.price_per_hour_cents::bigint * p_hours;
  IF w.available_cents < total THEN RAISE EXCEPTION 'INSUFFICIENT_FUNDS:%', total - w.available_cents; END IF;
  UPDATE public.wallets SET available_cents = available_cents - total, updated_at = now() WHERE user_id = uid;
  UPDATE public.facilities SET available = LEAST(available, v_remaining) - 1 WHERE id = f.id;
  INSERT INTO public.bookings(user_id,facility_id,start_at,end_at,hours,total_cents,idempotency_key)
    VALUES (uid,f.id,p_start_at,p_start_at + make_interval(hours => p_hours),p_hours,total,p_idempotency_key) RETURNING * INTO b;
  INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,booking_id,description,idempotency_key)
    VALUES (uid,'booking_charge',-total,'succeeded',b.id,'Parking at ' || f.name,'charge-' || b.id);
  RETURN b;
END $$;

-- ── cancel_booking: facility lock before status flip; capped restore ──────
CREATE OR REPLACE FUNCTION public.cancel_booking(p_booking_id uuid)
RETURNS public.bookings LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE uid uuid := auth.uid(); b public.bookings; refund bigint; authorized integer; f public.facilities; v_confirmed bigint;
BEGIN
  IF uid IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  SELECT * INTO b FROM public.bookings WHERE id = p_booking_id AND user_id = uid FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'BOOKING_NOT_FOUND'; END IF;
  IF b.status <> 'confirmed' THEN RETURN b; END IF;
  PERFORM 1 FROM public.wallets WHERE user_id = uid FOR UPDATE;
  IF now() <= b.start_at - interval '2 hours' THEN refund := b.total_cents;
  ELSIF now() < b.start_at THEN refund := b.total_cents / 2;
  ELSE refund := 0; END IF;
  -- Facility lock BEFORE the status flip serializes the confirmed count
  -- against create_booking (which counts under the same lock).
  SELECT * INTO f FROM public.facilities WHERE id = b.facility_id FOR UPDATE;
  authorized := COALESCE(f.authorized_capacity, f.capacity);
  UPDATE public.bookings SET status = 'cancelled', refunded_cents = refund WHERE id = b.id RETURNING * INTO b;
  SELECT COUNT(*) INTO v_confirmed FROM public.bookings
    WHERE facility_id = b.facility_id AND status = 'confirmed';
  -- Option A semantics: one space returns to sale, but never above the
  -- authorized remaining computed from real confirmed bookings.
  UPDATE public.facilities
    SET available = LEAST(available + 1, GREATEST(0, authorized - v_confirmed::integer))
    WHERE id = b.facility_id;
  IF refund > 0 THEN
    UPDATE public.wallets SET available_cents = available_cents + refund, updated_at = now() WHERE user_id = uid;
    INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,booking_id,description,idempotency_key)
      VALUES (uid,'refund',refund,'succeeded',b.id,'Booking refund','refund-' || b.id);
  END IF;
  RETURN b;
END $$;

-- ── admin_cancel_booking: same locking and capped restore; audit kept ─────
CREATE OR REPLACE FUNCTION public.admin_cancel_booking(p_booking_id uuid, p_reason text)
RETURNS public.bookings LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE actor uuid := auth.uid(); b public.bookings; refund bigint; authorized integer; f public.facilities; v_confirmed bigint;
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
  SELECT * INTO f FROM public.facilities WHERE id = b.facility_id FOR UPDATE;
  authorized := COALESCE(f.authorized_capacity, f.capacity);
  UPDATE public.bookings SET status = 'cancelled', refunded_cents = refund WHERE id = b.id RETURNING * INTO b;
  SELECT COUNT(*) INTO v_confirmed FROM public.bookings
    WHERE facility_id = b.facility_id AND status = 'confirmed';
  UPDATE public.facilities
    SET available = LEAST(available + 1, GREATEST(0, authorized - v_confirmed::integer))
    WHERE id = b.facility_id;
  IF refund > 0 THEN
    UPDATE public.wallets SET available_cents = available_cents + refund, updated_at = now() WHERE user_id = b.user_id;
    INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,booking_id,description,idempotency_key)
      VALUES (b.user_id,'refund',refund,'succeeded',b.id,'Admin cancellation refund','refund-' || b.id);
  END IF;
  INSERT INTO public.audit_logs(actor_id,action,target_type,target_id,reason,metadata)
    VALUES (actor,'booking.cancel','booking',b.id::text,p_reason,jsonb_build_object('refund_cents',refund,'user_id',b.user_id));
  RETURN b;
END $$;

REVOKE EXECUTE ON FUNCTION public.create_booking(uuid,timestamptz,integer,text), public.cancel_booking(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.create_booking(uuid,timestamptz,integer,text), public.cancel_booking(uuid) TO authenticated;
REVOKE EXECUTE ON FUNCTION public.admin_cancel_booking(uuid,text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_cancel_booking(uuid,text) TO authenticated;

-- ── capacity-change clamp trigger ──────────────────────────────────────────
-- SECURITY DEFINER (owned by the migration role, like create_booking) so
-- the confirmed count sees ALL bookings regardless of which admin/partner
-- fired the facilities UPDATE — an invoker function would silently
-- undercount if the bookings SELECT policy ever tightened. The function
-- takes no arguments, returns only trigger, and can only LOWER
-- NEW.available, so it exposes no booking data and cannot escalate
-- privileges. Direct RPC invocation is revoked below; trigger firing does
-- not depend on the firing user's EXECUTE grant.
CREATE OR REPLACE FUNCTION public.clamp_available_to_authorized()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_confirmed bigint;
BEGIN
  SELECT COUNT(*) INTO v_confirmed FROM public.bookings
    WHERE facility_id = NEW.id AND status = 'confirmed';
  -- Ceiling-only: clamp the incoming value down to the authorized
  -- remaining; never raise it (an authorized increase alone must not
  -- resurrect spaces Ops had manually removed).
  NEW.available := LEAST(NEW.available,
    GREATEST(0, COALESCE(NEW.authorized_capacity, NEW.capacity) - v_confirmed::integer));
  RETURN NEW;
END $$;

REVOKE EXECUTE ON FUNCTION public.clamp_available_to_authorized() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS facilities_clamp_available_on_capacity ON public.facilities;
CREATE TRIGGER facilities_clamp_available_on_capacity
  BEFORE UPDATE OF authorized_capacity, total_capacity ON public.facilities
  FOR EACH ROW EXECUTE FUNCTION public.clamp_available_to_authorized();

-- ── one-time repair: lower inflated counters ONLY ──────────────────────────
-- LEAST(...) can never raise a value, and the WHERE clause touches only
-- rows above the authorized remaining, so manual reductions below the
-- computed remainder (maintenance corrections) survive the migration.
UPDATE public.facilities f
SET available = LEAST(f.available,
      GREATEST(0, COALESCE(f.authorized_capacity, f.capacity)
        - (SELECT COUNT(*) FROM public.bookings b
             WHERE b.facility_id = f.id AND b.status = 'confirmed')::integer))
WHERE f.available > GREATEST(0, COALESCE(f.authorized_capacity, f.capacity)
        - (SELECT COUNT(*) FROM public.bookings b
             WHERE b.facility_id = f.id AND b.status = 'confirmed')::integer);
