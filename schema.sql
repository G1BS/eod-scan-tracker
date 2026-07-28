-- ============================================================
-- EOD Scan Tracker — Supabase schema
-- Run this once in Supabase SQL Editor (Project -> SQL Editor -> New query)
-- ============================================================

create extension if not exists "pgcrypto";

create table if not exists scan_results (
  id          uuid primary key default gen_random_uuid(),
  scan_date   date not null,
  strategy    text not null,          -- e.g. 'VCP', 'Multi-touch Support', 'PEAD', 'Regime', 'StatArb'
  ticker      text not null,
  score       numeric,                -- 0-100 conviction score, nullable if a strategy doesn't score
  stage       text,                   -- e.g. 'Stage 2 Late IB', 'Breakout confirmed', free text per strategy
  entry       numeric,
  stop        numeric,
  target      numeric,
  extra       jsonb default '{}'::jsonb,   -- any strategy-specific fields you don't want to schema-ize
  notes       text default '',
  taken       boolean default false,
  created_at  timestamptz default now(),

  unique (scan_date, strategy, ticker)  -- re-running a scan for the same day upserts, doesn't duplicate
);

create index if not exists idx_scan_date_strategy on scan_results (scan_date, strategy);
create index if not exists idx_scan_ticker on scan_results (ticker);

-- ------------------------------------------------------------
-- Security: this is a single-user private app.
-- We use Supabase Auth (magic-link email login) and lock every
-- row operation to logged-in requests only. Since you'll be the
-- only account that ever signs up, this is a simple, effective wall.
-- ------------------------------------------------------------
alter table scan_results enable row level security;

create policy "authenticated read" on scan_results
  for select using (auth.role() = 'authenticated');

create policy "authenticated update" on scan_results
  for update using (auth.role() = 'authenticated');

-- Inserts happen from GitHub Actions using the service_role key,
-- which bypasses RLS entirely, so no insert policy for 'authenticated'
-- is needed (keeps the phone app read/annotate-only, not able to
-- inject fake scan rows).
