-- ═══════════════════════════════════════════════════════════════════════════
-- ParkSpot AI — COMPLETE SETUP FOR A NEW (EMPTY) SUPABASE DATABASE
--
-- Creates EVERYTHING the app needs, in one paste:
--   PART 1  core schema: profiles, roles, facilities (+6 seeded car parks),
--           wallets, bookings, money functions, signup trigger, RLS policies
--   PART 2  Super Admin: capacity columns, audit log, cameras, incidents,
--           app settings, admin policies, admin money functions
--
-- HOW TO RUN
--   1. Open your NEW project → SQL Editor:
--      https://supabase.com/dashboard/project/aeptcbtlplnrvrxjpxre/sql/new
--   2. Paste this WHOLE file and click Run.
--   3. It runs inside one transaction: if anything errors, NOTHING is
--      applied, so fix the error and run it again safely.
--   4. Success check: the last query lists the 6 seeded parking facilities.
--
-- AFTER THIS: run scripts/seed_demo_users.sql the same way to create the
-- admin@demo.test / partner@demo.test / driver@demo.test accounts.
-- ═══════════════════════════════════════════════════════════════════════════

begin;

-- ════════════════════════ PART 1 — CORE SCHEMA ════════════════════════════

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
  available_cents bigint NOT
...[truncated 17945 chars]