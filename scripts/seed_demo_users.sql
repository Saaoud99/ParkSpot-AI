-- ParkSpot AI — demo accounts seed (3 users, 3 different roles). v2
--
-- WHY v2: the first version set auth.identities.provider_id, which does not
-- exist on every Supabase version. If that column is missing, the whole
-- transaction rolls back and NO user is created, so every login fails with
-- "Invalid login credentials". This version omits it (GoTrue fills it in).
--
-- HOW TO RUN: Supabase Dashboard (project aeptcbtlplnrvrxjpxre) → SQL Editor
-- → paste this whole file → Run. Safe to re-run: old demo users are removed
-- first. The final SELECT must show 3 rows with password_ok = true.
--
-- Passwords are demo-only and public by design. Delete these accounts
-- (or change the passwords) before real users get access.

begin;

-- ── clean slate for re-runs ────────────────────────────────────────────────
-- wallets.user_id has no FK to auth.users, so remove wallets explicitly;
-- profiles / user_roles / identities cascade from auth.users.
delete from public.wallets
 where user_id in (select id from auth.users
                   where email in ('admin@demo.test', 'partner@demo.test', 'driver@demo.test'));
delete from auth.users
 where email in ('admin@demo.test', 'partner@demo.test', 'driver@demo.test');

-- ── 1) SUPER ADMIN ─────────────────────────────────────────────────────────
insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'a0000000-0000-0000-0000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'admin@demo.test',
  extensions.crypt('Admin123', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"full_name":"Demo Admin"}'::jsonb,
  now(), now()
);
insert into auth.identities (id, user_id, provider, identity_data, last_sign_in_at, created_at, updated_at)
values (
  'a0000000-0000-0000-0000-000000000001',
  'a0000000-0000-0000-0000-000000000001',
  'email',
  jsonb_build_object('sub', 'a0000000-0000-0000-0000-000000000001', 'email', 'admin@demo.test', 'email_verified', true),
  now(), now(), now()
);

-- ── 2) PARTNER ─────────────────────────────────────────────────────────────
insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'a0000000-0000-0000-0000-000000000002',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'partner@demo.test',
  extensions.crypt('Partner123', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"full_name":"Demo Partner"}'::jsonb,
  now(), now()
);
insert into auth.identities (id, user_id, provider, identity_data, last_sign_in_at, created_at, updated_at)
values (
  'a0000000-0000-0000-0000-000000000002',
  'a0000000-0000-0000-0000-000000000002',
  'email',
  jsonb_build_object('sub', 'a0000000-0000-0000-0000-000000000002', 'email', 'partner@demo.test', 'email_verified', true),
  now(), now(), now()
);

-- ── 3) DRIVER (regular user) ───────────────────────────────────────────────
insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
) values (
  'a0000000-0000-0000-0000-000000000003',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated',
  'driver@demo.test',
  extensions.crypt('Driver123', extensions.gen_salt('bf')),
  now(),
  '{"provider":"email","providers":["email"]}'::jsonb,
  '{"full_name":"Demo Driver"}'::jsonb,
  now(), now()
);
insert into auth.identities (id, user_id, provider, identity_data, last_sign_in_at, created_at, updated_at)
values (
  'a0000000-0000-0000-0000-000000000003',
  'a0000000-0000-0000-0000-000000000003',
  'email',
  jsonb_build_object('sub', 'a0000000-0000-0000-0000-000000000003', 'email', 'driver@demo.test', 'email_verified', true),
  now(), now(), now()
);

-- The handle_new_user trigger already created a profile, an empty wallet,
-- and the 'user' role for each account. Give admin/partner exactly their
-- demo role, and fill in profile details.
delete from public.user_roles
 where user_id = 'a0000000-0000-0000-0000-000000000001' and role = 'user';
insert into public.user_roles (user_id, role)
 values ('a0000000-0000-0000-0000-000000000001', 'admin')
 on conflict do nothing;

delete from public.user_roles
 where user_id = 'a0000000-0000-0000-0000-000000000002' and role = 'user';
insert into public.user_roles (user_id, role)
 values ('a0000000-0000-0000-0000-000000000002', 'partner')
 on conflict do nothing;
-- driver keeps the trigger's 'user' role.

update public.profiles
   set display_name = 'Demo Admin', phone = '+212600000001'
 where id = 'a0000000-0000-0000-0000-000000000001';
update public.profiles
   set display_name = 'Demo Partner', phone = '+212600000002'
 where id = 'a0000000-0000-0000-0000-000000000002';
update public.profiles
   set display_name = 'Demo Driver', phone = '+212600000003',
       vehicle_plate = '12345-A-6', vehicle_model = 'Dacia Logan'
 where id = 'a0000000-0000-0000-0000-000000000003';

commit;

-- VERIFY: expect exactly 3 rows, every password_ok = true, roles
-- admin / partner / user. If this shows 3 true rows, sign-in WILL work
-- with the passwords below — the problem is then the app instance
-- being tested, not the database.
select u.email, r.role,
       u.email_confirmed_at is not null as confirmed,
       case u.email
         when 'admin@demo.test'   then u.encrypted_password = extensions.crypt('Admin123',   u.encrypted_password)
         when 'partner@demo.test' then u.encrypted_password = extensions.crypt('Partner123', u.encrypted_password)
         when 'driver@demo.test'  then u.encrypted_password = extensions.crypt('Driver123',  u.encrypted_password)
       end as password_ok
  from auth.users u
  join public.user_roles r on r.user_id = u.id
 where u.email in ('admin@demo.test', 'partner@demo.test', 'driver@demo.test')
 order by u.email;
