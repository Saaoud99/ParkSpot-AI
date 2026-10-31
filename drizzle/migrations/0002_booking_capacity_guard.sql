-- 0002_booking_capacity_guard.sql — booking must respect authorized capacity.
-- Apply AFTER 0000_migration.sql and 0001_admin.sql, in the Supabase SQL editor.
-- Additive: replaces only the two booking functions. No data is changed.
--
-- Why: 0001 introduced total_capacity vs authorized_capacity (and the
-- facilities.active flag), but create_booking/cancel_booking from 0000 still
-- used the legacy `capacity` column and ignored `active`. From now on:
--   * a deactivated facility cannot be booked at all (FACILITY_INACTIVE);
--   * cancellations restore availability only up to authorized_capacity;
--   * authorized_capacity falls back to `capacity` when NULL (pre-0001 rows).

CREATE OR REPLACE FUNCTION public.create_booking(p_facility_id uuid, p_start_at timestamptz, p_hours integer, p_idempotency_key text)
RETURNS public.bookings LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE uid uuid := auth.uid(); f public.facilities; w public.wallets; b public.bookings; total bigint; authorized integer;
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
  -- Effective free spaces can never exceed the authorized capacity, even
  -- if a stale `available` value is higher.
  IF LEAST(f.available, authorized) < 1 THEN RAISE EXCEPTION 'FACILITY_FULL'; END IF;
  total := f.price_per_hour_cents::bigint * p_hours;
  IF w.available_cents < total THEN RAISE EXCEPTION 'INSUFFICIENT_FUNDS:%', total - w.available_cents; END IF;
  UPDATE public.wallets SET available_cents = available_cents - total, updated_at = now() WHERE user_id = uid;
  UPDATE public.facilities SET available = LEAST(available, authorized) - 1 WHERE id = f.id;
  INSERT INTO public.bookings(user_id,facility_id,start_at,end_at,hours,total_cents,idempotency_key)
    VALUES (uid,f.id,p_start_at,p_start_at + make_interval(hours => p_hours),p_hours,total,p_idempotency_key) RETURNING * INTO b;
  INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,booking_id,description,idempotency_key)
    VALUES (uid,'booking_charge',-total,'succeeded',b.id,'Parking at ' || f.name,'charge-' || b.id);
  RETURN b;
END $$;

CREATE OR REPLACE FUNCTION public.cancel_booking(p_booking_id uuid)
RETURNS public.bookings LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE uid uuid := auth.uid(); b public.bookings; refund bigint; authorized integer; f public.facilities;
BEGIN
  IF uid IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  SELECT * INTO b FROM public.bookings WHERE id = p_booking_id AND user_id = uid FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'BOOKING_NOT_FOUND'; END IF;
  IF b.status <> 'confirmed' THEN RETURN b; END IF;
  PERFORM 1 FROM public.wallets WHERE user_id = uid FOR UPDATE;
  IF now() <= b.start_at - interval '2 hours' THEN refund := b.total_cents;
  ELSIF now() < b.start_at THEN refund := b.total_cents / 2;
  ELSE refund := 0; END IF;
  SELECT * INTO f FROM public.facilities WHERE id = b.facility_id;
  authorized := COALESCE(f.authorized_capacity, f.capacity);
  UPDATE public.bookings SET status = 'cancelled', refunded_cents = refund WHERE id = b.id RETURNING * INTO b;
  UPDATE public.facilities SET available = LEAST(authorized, available + 1) WHERE id = b.facility_id;
  IF refund > 0 THEN
    UPDATE public.wallets SET available_cents = available_cents + refund, updated_at = now() WHERE user_id = uid;
    INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,booking_id,description,idempotency_key)
      VALUES (uid,'refund',refund,'succeeded',b.id,'Booking refund','refund-' || b.id);
  END IF;
  RETURN b;
END $$;

REVOKE EXECUTE ON FUNCTION public.create_booking(uuid,timestamptz,integer,text), public.cancel_booking(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.create_booking(uuid,timestamptz,integer,text), public.cancel_booking(uuid) TO authenticated;
