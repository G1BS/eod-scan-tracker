// Supabase Edge Function: get-quote
// Fetches the latest daily close price for an NSE ticker (server-side, avoids
// browser CORS restrictions). Called from the PWA when adding a watchlist stock.

import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }

  try {
    const { ticker } = await req.json();
    if (!ticker) throw new Error("ticker is required");

    const symbol = ticker.includes(".") ? ticker.toUpperCase() : `${ticker.toUpperCase()}.NS`;
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${symbol}?interval=1d&range=5d`;

    const resp = await fetch(url, { headers: { "User-Agent": "Mozilla/5.0" } });
    if (!resp.ok) throw new Error(`Quote source returned ${resp.status}`);
    const data = await resp.json();

    const result = data?.chart?.result?.[0];
    if (!result) throw new Error(`No data found for ${symbol}`);

    const closes: (number | null)[] = result.indicators.quote[0].close;
    const timestamps: number[] = result.timestamp;

    let idx = closes.length - 1;
    while (idx >= 0 && (closes[idx] === null || closes[idx] === undefined)) idx--;
    if (idx < 0) throw new Error(`No valid close price for ${symbol}`);

    const price = Math.round(closes[idx] * 100) / 100;
    const priceDate = new Date(timestamps[idx] * 1000).toISOString().slice(0, 10);

    return new Response(JSON.stringify({ price, date: priceDate }), {
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 400,
      headers: { ...CORS_HEADERS, "Content-Type": "application/json" },
    });
  }
});
