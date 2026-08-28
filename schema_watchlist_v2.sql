-- ============================================================
-- Watchlist v2 — run this in Supabase SQL Editor
-- Additive only: adds columns needed for "Track" button + auto price fetch
-- ============================================================

-- Marks which scan rows have already been converted into a tracked watchlist item
alter table scan_results add column if not exists tracked boolean default false;

-- Where a watchlist item came from: 'VCP' / 'Swing Screener' / 'Manual'
alter table watchlist_items add column if not exists source_strategy text default 'Manual';

-- Traceability back to the original scan row, if tracked from a scan (nullable for manual adds)
alter table watchlist_items add column if not exists source_scan_id uuid references scan_results(id);

create index if not exists idx_scan_tracked on scan_results (tracked);
create index if not exists idx_watchlist_source on watchlist_items (source_strategy);
