CREATE TYPE public.app_role AS ENUM ('admin','partner','user');

CREATE TABLE public.profiles (
  id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  display_name text, phone text, vehicle_plate text, vehicle_model text,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT, UPDATE ON public.profiles TO authenticated;
GRANT ALL ON public.profiles TO service_role;
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own profile read" ON public.profiles FOR SELECT TO authenticated USING (auth.uid() = id);
CREATE POLICY "own profile update" ON public.profiles FOR UPDATE TO authenticated USING (auth.uid() = id) WITH CHECK (auth.uid() = id);

CREATE TABLE public.user_roles (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role public.app_role NOT NULL,
  UNIQUE (user_id, role)
);
GRANT SELECT ON public.user_roles TO authenticated;
GRANT ALL ON public.user_roles TO service_role;
ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own roles read" ON public.user_roles FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.has_role(_user_id uuid, _role public.app_role)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM public.user_roles WHERE user_id = _user_id AND role = _role)
$$;

CREATE TABLE public.facilities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL, name_ar text NOT NULL,
  city text NOT NULL, address text NOT NULL,
  lat double precision NOT NULL, lng double precision NOT NULL,
  price_per_hour_cents integer NOT NULL CHECK (price_per_hour_cents > 0),
  capacity integer NOT NULL CHECK (capacity >= 0),
  available integer NOT NULL CHECK (available >= 0),
  image_key text NOT NULL DEFAULT 'garage',
  features text[] NOT NULL DEFAULT '{}',
  rating numeric(2,1) NOT NULL DEFAULT 4.5,
  open_24h boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.facilities TO anon, authenticated;
GRANT UPDATE ON public.facilities TO authenticated;
GRANT ALL ON public.facilities TO service_role;
ALTER TABLE public.facilities ENABLE ROW LEVEL SECURITY;
CREATE POLICY "public read facilities" ON public.facilities FOR SELECT TO anon, authenticated USING (true);
CREATE POLICY "ops update facilities" ON public.facilities FOR UPDATE TO authenticated
  USING (public.has_role(auth.uid(),'admin') OR public.has_role(auth.uid(),'partner'))
  WITH CHECK (public.has_role(auth.uid(),'admin') OR public.has_role(auth.uid(),'partner'));

CREATE TABLE public.wallets (
  user_id uuid PRIMARY KEY,
  available_cents bigint NOT NULL DEFAULT 0 CHECK (available_cents >= 0),
  reserved_cents bigint NOT NULL DEFAULT 0 CHECK (reserved_cents >= 0),
  total_deposited_cents bigint NOT NULL DEFAULT 0,
  currency text NOT NULL DEFAULT 'MAD',
  is_demo boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.wallets TO authenticated;
GRANT ALL ON public.wallets TO service_role;
ALTER TABLE public.wallets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own wallet read" ON public.wallets FOR SELECT TO authenticated USING (auth.uid() = user_id);

CREATE TABLE public.bookings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  facility_id uuid NOT NULL REFERENCES public.facilities(id),
  start_at timestamptz NOT NULL,
  end_at timestamptz NOT NULL,
  hours integer NOT NULL CHECK (hours BETWEEN 1 AND 24),
  total_cents bigint NOT NULL,
  refunded_cents bigint NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed','cancelled','completed')),
  access_code text NOT NULL DEFAULT upper(substr(md5(random()::text),1,8)),
  idempotency_key text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.bookings TO authenticated;
GRANT ALL ON public.bookings TO service_role;
ALTER TABLE public.bookings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own bookings read" ON public.bookings FOR SELECT TO authenticated
  USING (auth.uid() = user_id OR public.has_role(auth.uid(),'admin') OR public.has_role(auth.uid(),'partner'));

CREATE TABLE public.wallet_transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  type text NOT NULL CHECK (type IN ('topup','booking_charge','refund')),
  amount_cents bigint NOT NULL,
  status text NOT NULL CHECK (status IN ('succeeded','failed','pending')),
  reference text NOT NULL DEFAULT ('PS-' || upper(substr(md5(random()::text),1,10))),
  booking_id uuid REFERENCES public.bookings(id),
  description text NOT NULL,
  is_demo boolean NOT NULL DEFAULT true,
  idempotency_key text UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now()
);
GRANT SELECT ON public.wallet_transactions TO authenticated;
GRANT ALL ON public.wallet_transactions TO service_role;
ALTER TABLE public.wallet_transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "own tx read" ON public.wallet_transactions FOR SELECT TO authenticated USING (auth.uid() = user_id);

-- signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  INSERT INTO public.profiles(id, display_name) VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'full_name', NEW.raw_user_meta_data->>'name', split_part(NEW.email,'@',1)));
  INSERT INTO public.wallets(user_id) VALUES (NEW.id);
  INSERT INTO public.user_roles(user_id, role) VALUES (NEW.id, 'user');
  RETURN NEW;
END $$;
CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- demo top-up
CREATE OR REPLACE FUNCTION public.demo_topup(p_amount_cents bigint, p_outcome text, p_idempotency_key text)
RETURNS public.wallet_transactions LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE uid uuid := auth.uid(); tx public.wallet_transactions;
BEGIN
  IF uid IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  IF p_amount_cents < 1000 OR p_amount_cents > 500000 THEN RAISE EXCEPTION 'INVALID_AMOUNT'; END IF;
  IF p_outcome NOT IN ('succeeded','failed','pending') THEN RAISE EXCEPTION 'INVALID_OUTCOME'; END IF;
  SELECT * INTO tx FROM public.wallet_transactions WHERE idempotency_key = p_idempotency_key AND user_id = uid;
  IF FOUND THEN RETURN tx; END IF;
  INSERT INTO public.wallets(user_id) VALUES (uid) ON CONFLICT DO NOTHING;
  PERFORM 1 FROM public.wallets WHERE user_id = uid FOR UPDATE;
  INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,description,idempotency_key)
    VALUES (uid,'topup',p_amount_cents,p_outcome,'Demo top-up',p_idempotency_key) RETURNING * INTO tx;
  IF p_outcome = 'succeeded' THEN
    UPDATE public.wallets SET available_cents = available_cents + p_amount_cents,
      total_deposited_cents = total_deposited_cents + p_amount_cents, updated_at = now() WHERE user_id = uid;
  END IF;
  RETURN tx;
END $$;

-- booking paid by wallet
CREATE OR REPLACE FUNCTION public.create_booking(p_facility_id uuid, p_start_at timestamptz, p_hours integer, p_idempotency_key text)
RETURNS public.bookings LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE uid uuid := auth.uid(); f public.facilities; w public.wallets; b public.bookings; total bigint;
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
  IF f.available < 1 THEN RAISE EXCEPTION 'FACILITY_FULL'; END IF;
  total := f.price_per_hour_cents::bigint * p_hours;
  IF w.available_cents < total THEN RAISE EXCEPTION 'INSUFFICIENT_FUNDS:%', total - w.available_cents; END IF;
  UPDATE public.wallets SET available_cents = available_cents - total, updated_at = now() WHERE user_id = uid;
  UPDATE public.facilities SET available = available - 1 WHERE id = f.id;
  INSERT INTO public.bookings(user_id,facility_id,start_at,end_at,hours,total_cents,idempotency_key)
    VALUES (uid,f.id,p_start_at,p_start_at + make_interval(hours => p_hours),p_hours,total,p_idempotency_key) RETURNING * INTO b;
  INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,booking_id,description,idempotency_key)
    VALUES (uid,'booking_charge',-total,'succeeded',b.id,'Parking at ' || f.name,'charge-' || b.id);
  RETURN b;
END $$;

-- cancel with refund policy: >=2h before start full, before start 50%, after start none
CREATE OR REPLACE FUNCTION public.cancel_booking(p_booking_id uuid)
RETURNS public.bookings LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE uid uuid := auth.uid(); b public.bookings; refund bigint;
BEGIN
  IF uid IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  SELECT * INTO b FROM public.bookings WHERE id = p_booking_id AND user_id = uid FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'BOOKING_NOT_FOUND'; END IF;
  IF b.status <> 'confirmed' THEN RETURN b; END IF;
  PERFORM 1 FROM public.wallets WHERE user_id = uid FOR UPDATE;
  IF now() <= b.start_at - interval '2 hours' THEN refund := b.total_cents;
  ELSIF now() < b.start_at THEN refund := b.total_cents / 2;
  ELSE refund := 0; END IF;
  UPDATE public.bookings SET status = 'cancelled', refunded_cents = refund WHERE id = b.id RETURNING * INTO b;
  UPDATE public.facilities SET available = LEAST(capacity, available + 1) WHERE id = b.facility_id;
  IF refund > 0 THEN
    UPDATE public.wallets SET available_cents = available_cents + refund, updated_at = now() WHERE user_id = uid;
    INSERT INTO public.wallet_transactions(user_id,type,amount_cents,status,booking_id,description,idempotency_key)
      VALUES (uid,'refund',refund,'succeeded',b.id,'Booking refund','refund-' || b.id);
  END IF;
  RETURN b;
END $$;

REVOKE EXECUTE ON FUNCTION public.demo_topup(bigint,text,text), public.create_booking(uuid,timestamptz,integer,text), public.cancel_booking(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.demo_topup(bigint,text,text), public.create_booking(uuid,timestamptz,integer,text), public.cancel_booking(uuid) TO authenticated;

INSERT INTO public.facilities(name,name_ar,city,address,lat,lng,price_per_hour_cents,capacity,available,image_key,features,rating) VALUES
('Casa Marina Parking','موقف كازا مارينا','Casablanca','Boulevard des Almohades',33.6060,-7.6260,1500,320,84,'garage','{covered,ev,cctv}',4.8),
('Twin Center Garage','مرآب توين سنتر','Casablanca','Boulevard Zerktouni',33.5890,-7.6320,2000,220,31,'underground','{covered,cctv,valet}',4.6),
('Maârif Open Lot','موقف المعاريف','Casablanca','Rue Ibnou Mounir',33.5830,-7.6390,800,90,22,'openlot','{cctv}',4.3),
('Agdal Smart Park','موقف أكدال الذكي','Rabat','Avenue de France',33.9980,-6.8520,1200,180,57,'rooftop','{ev,covered}',4.7),
('Gueliz Central','مركز كليز','Marrakech','Avenue Mohammed V',31.6340,-8.0100,1000,150,40,'garage','{cctv,covered}',4.5),
('Tanger City Center','طنجة سيتي سنتر','Tangier','Route de Rabat',35.7600,-5.8300,1300,260,0,'underground','{covered,ev,cctv}',4.4);