-- ============================================================
-- Watchlist feature — run this in Supabase SQL Editor
-- (additive: doesn't touch your existing scan_results table)
-- ============================================================

create table if not exists watchlist_items (
  id                 uuid primary key default gen_random_uuid(),
  ticker             text not null,               -- e.g. 'RELIANCE' (NSE assumed unless you type an exchange suffix)
  added_at           timestamptz default now(),
  entry_price        numeric not null,
  direction          text not null default 'bullish',  -- 'bullish' or 'bearish'
  target             numeric,                      -- optional
  reason             text default '',              -- optional note: why you shortlisted it
  status             text default 'active',        -- 'active' or 'closed' (you archive it manually)
  latest_price       numeric,                      -- filled in daily by the automation
  latest_price_date  date,
  pct_change         numeric,                       -- % move from entry, signed to your direction
  peak_favorable_pct numeric default 0,             -- best % move in your favor ever recorded, used to detect reversals
  computed_status    text default 'Flat',           -- 'As Expected' | 'Against Expectation' | 'Reversed' | 'Flat' | 'Target Hit'
  created_at         timestamptz default now()
);

create table if not exists watchlist_price_history (
  id             uuid primary key default gen_random_uuid(),
  watchlist_id   uuid references watchlist_items(id) on delete cascade,
  price_date     date not null,
  price          numeric not null,
  created_at     timestamptz default now(),
  unique (watchlist_id, price_date)
);

create index if not exists idx_watchlist_status on watchlist_items (status);
create index if not exists idx_watchlist_history_id on watchlist_price_history (watchlist_id);

-- ------------------------------------------------------------
-- RLS: same single-user model as scan_results, EXCEPT here we
-- also allow authenticated INSERT — this table is meant to be
-- written to from your phone when you shortlist something.
-- ------------------------------------------------------------
alter table watchlist_items enable row level security;
alter table watchlist_price_history enable row level security;

create policy "authenticated read watchlist" on watchlist_items
  for select using (auth.role() = 'authenticated');
create policy "authenticated insert watchlist" on watchlist_items
  for insert with check (auth.role() = 'authenticated');
create policy "authenticated update watchlist" on watchlist_items
  for update using (auth.role() = 'authenticated');
create policy "authenticated delete watchlist" on watchlist_items
  for delete using (auth.role() = 'authenticated');

create policy "authenticated read watchlist history" on watchlist_price_history
  for select using (auth.role() = 'authenticated');
-- No insert/update policy for history from the app — only the
-- GitHub Actions job (using the service_role key, which bypasses
-- RLS) writes daily prices, so you can't accidentally corrupt it.
