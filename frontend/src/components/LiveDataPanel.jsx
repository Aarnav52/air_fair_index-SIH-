import React, { useState, useEffect, useCallback } from 'react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';
import {
  RefreshCw, Plane, Activity, Database, AlertCircle, CheckCircle2, Loader2,
  TrendingDown, ArrowUpRight,
} from 'lucide-react';
import {
  fetchRoutes, fetchFlights, triggerScrape, fetchIndex, fetchHealth,
} from '../api/apiService';

// ─── Small helpers ─────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  const map = {
    healthy:   'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    error:     'bg-rose-500/10   text-rose-400   border-rose-500/30',
    loading:   'bg-sky-500/10    text-sky-400    border-sky-500/30',
  };
  const cls = map[status] || map.loading;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold border ${cls}`}>
      <span className="w-1.5 h-1.5 rounded-full bg-current animate-pulse" />
      {status === 'healthy' ? 'BACKEND LIVE' : status === 'error' ? 'BACKEND DOWN' : 'CONNECTING…'}
    </span>
  );
}

function MetricCard({ label, value, sub, highlight = 'text-white' }) {
  return (
    <div className="glass-panel p-4 rounded-2xl glass-card-glow">
      <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">{label}</span>
      <span className={`text-2xl font-extrabold font-mono mt-1 block ${highlight}`}>{value}</span>
      {sub && <span className="text-[11px] text-slate-500 mt-1 block">{sub}</span>}
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────

export default function LiveDataPanel() {
  const [backendStatus, setBackendStatus] = useState('loading'); // 'loading' | 'healthy' | 'error'
  const [routes,        setRoutes]        = useState([]);
  const [selectedRoute, setSelectedRoute] = useState('DEL-BOM');
  const [selectedWindow,setSelectedWindow]= useState('T+1');
  const [flights,       setFlights]       = useState([]);
  const [indexData,     setIndexData]     = useState(null);
  const [scrapeResult,  setScrapeResult]  = useState(null);

  const [loadingFlights, setLoadingFlights] = useState(false);
  const [loadingIndex,   setLoadingIndex]   = useState(false);
  const [scraping,       setScraping]       = useState(false);
  const [error,          setError]          = useState('');

  // ── Health check ─────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchHealth()
      .then(() => setBackendStatus('healthy'))
      .catch(() => setBackendStatus('error'));
  }, []);

  // ── Routes ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    fetchRoutes()
      .then(setRoutes)
      .catch(() => {});
  }, []);

  // ── Flights ──────────────────────────────────────────────────────────────────
  const loadFlights = useCallback(() => {
    setLoadingFlights(true);
    setError('');
    fetchFlights(selectedRoute, selectedWindow)
      .then(setFlights)
      .catch(e => setError(e.message))
      .finally(() => setLoadingFlights(false));
  }, [selectedRoute, selectedWindow]);

  // ── Index ────────────────────────────────────────────────────────────────────
  const loadIndex = useCallback(() => {
    setLoadingIndex(true);
    fetchIndex(selectedRoute, selectedWindow)
      .then(setIndexData)
      .catch(() => setIndexData(null))
      .finally(() => setLoadingIndex(false));
  }, [selectedRoute, selectedWindow]);

  // Reload when selections change
  useEffect(() => {
    loadFlights();
    loadIndex();
  }, [selectedRoute, selectedWindow]);

  // ── Scrape trigger ───────────────────────────────────────────────────────────
  const handleScrape = async () => {
    const [origin, dest] = selectedRoute.split('-');
    setScraping(true);
    setScrapeResult(null);
    try {
      const result = await triggerScrape(origin, dest, [selectedWindow]);
      setScrapeResult(result);
      // Reload data after scrape
      await loadFlights();
      await loadIndex();
    } catch (e) {
      setError(e.message);
    } finally {
      setScraping(false);
    }
  };

  // ── Derived stats ─────────────────────────────────────────────────────────────
  const prices = flights.map(f => f.price).filter(Boolean);
  const minPrice = prices.length ? Math.min(...prices) : null;
  const maxPrice = prices.length ? Math.max(...prices) : null;
  const avgPrice = prices.length ? (prices.reduce((a, b) => a + b, 0) / prices.length) : null;

  const currentIndex = indexData?.series?.at(-1)?.index_value;
  const baseIndex    = indexData?.base_avg_price;

  // Chart data from index series
  const chartData = (indexData?.series || []).map(s => ({
    date: s.date,
    indexValue: s.index_value,
    avgPrice: s.avg_price,
  }));

  // ── Render ────────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-6">

      {/* Panel Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <h3 className="text-lg font-bold text-white flex items-center gap-2">
            <Database className="w-5 h-5 text-sky-400" />
            Live Scraped Data
            <StatusBadge status={backendStatus} />
          </h3>
          <p className="text-xs text-slate-400 mt-1">
            Real observations from SerpApi Google Flights → Supabase PostgreSQL
          </p>
        </div>

        {/* Controls */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Route selector */}
          <select
            value={selectedRoute}
            onChange={e => setSelectedRoute(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-2 focus:outline-none focus:border-sky-500"
          >
            {routes.length > 0
              ? routes.map(r => (
                  <option key={r.route_id} value={r.route_code}>
                    {r.origin_airport} → {r.destination_airport} ({r.origin_city} – {r.destination_city})
                  </option>
                ))
              : <option value="DEL-BOM">DEL → BOM (Delhi – Mumbai)</option>
            }
          </select>

          {/* Window selector */}
          <select
            value={selectedWindow}
            onChange={e => setSelectedWindow(e.target.value)}
            className="bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-2 focus:outline-none focus:border-sky-500"
          >
            <option value="T+1">T+1 (Tomorrow)</option>
            <option value="T+30">T+30 (30 Days)</option>
          </select>

          {/* Refresh */}
          <button
            onClick={() => { loadFlights(); loadIndex(); }}
            disabled={loadingFlights}
            className="flex items-center gap-1.5 px-3 py-2 text-xs font-bold rounded-xl text-slate-200 bg-slate-900 border border-slate-700 hover:bg-slate-800 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-sky-400 ${loadingFlights ? 'animate-spin' : ''}`} />
            Refresh
          </button>

          {/* Scrape */}
          <button
            onClick={handleScrape}
            disabled={scraping || backendStatus !== 'healthy'}
            className="flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold rounded-xl text-white bg-sky-600 hover:bg-sky-500 border border-sky-500 transition-all disabled:opacity-50 shadow-md"
          >
            {scraping
              ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
              : <Plane className="w-3.5 h-3.5" />}
            {scraping ? 'Scraping…' : 'Scrape Now'}
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-xs text-rose-400">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Scrape Result Banner */}
      {scrapeResult && (
        <div className="flex items-start gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-300">
          <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
          <div>
            <span className="font-bold text-emerald-300">Scrape complete — {scrapeResult.status}</span>
            {scrapeResult.details?.map(d => (
              <div key={d.window} className="font-mono mt-1 text-emerald-400/80">
                {d.window} ({d.target_date}): {d.flights_found} found · {d.rows_inserted} inserted
                {d.error && <span className="text-rose-400 ml-2">⚠ {d.error}</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard
          label="Observations"
          value={flights.length.toLocaleString()}
          sub={`${selectedRoute} · ${selectedWindow}`}
          highlight="text-sky-400"
        />
        <MetricCard
          label="Min Fare"
          value={minPrice ? `₹${minPrice.toLocaleString()}` : '—'}
          sub="Cheapest observed"
          highlight="text-emerald-400"
        />
        <MetricCard
          label="Avg Fare"
          value={avgPrice ? `₹${Math.round(avgPrice).toLocaleString()}` : '—'}
          sub="Unweighted mean"
        />
        <MetricCard
          label="Jevons Index"
          value={currentIndex != null ? currentIndex.toFixed(2) : '—'}
          sub={baseIndex ? `Base avg ₹${Math.round(baseIndex).toLocaleString()}` : 'Awaiting data'}
          highlight={currentIndex > 100 ? 'text-rose-400' : currentIndex < 100 ? 'text-emerald-400' : 'text-amber-400'}
        />
      </div>

      {/* Index Chart (visible once any scraped index data exists) */}
      {chartData.length >= 1 && (
        <div className="glass-panel p-6 rounded-3xl border border-slate-800 space-y-4">
          <h4 className="text-sm font-bold text-white flex items-center gap-2">
            <Activity className="w-4 h-4 text-sky-400" />
            Jevons Price Index — Historical Series ({selectedRoute} · {selectedWindow})
            {chartData.length === 1 && (
              <span className="text-[10px] font-normal text-sky-400/70 ml-2 font-mono">
                (1 scrape day — more days = trend line)
              </span>
            )}
          </h4>
          <div className="w-full h-52">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="liveIndexGlow" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor="#38bdf8" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#0284c7" stopOpacity={0}   />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} domain={['dataMin - 5', 'dataMax + 5']} tickLine={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#090d16', borderColor: '#38bdf833', borderRadius: '10px', color: '#fff', fontSize: '11px' }}
                  formatter={(v, n) => n === 'indexValue' ? [`${v}`, 'Jevons Index'] : [`₹${v}`, 'Avg Price']}
                />
                <Area
                  type="monotone"
                  dataKey="indexValue"
                  name="indexValue"
                  stroke="#38bdf8"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#liveIndexGlow)"
                  dot={{ r: 5, fill: '#38bdf8', strokeWidth: 2, stroke: '#0ea5e9' }}
                  activeDot={{ r: 7 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-slate-500">
            Index base = 100 on <span className="font-mono text-slate-400">{indexData?.base_date}</span>.
            Values above 100 indicate fares rising vs the base day.
            {chartData.length === 1 && (
              <span className="text-sky-400/70 ml-1">Scrape again tomorrow to see daily movement.</span>
            )}
          </p>
        </div>
      )}

      {/* Flights Table */}
      <div className="glass-panel rounded-3xl border border-slate-800 overflow-hidden">
        <div className="p-5 border-b border-slate-800 flex items-center justify-between">
          <h4 className="text-sm font-bold text-white flex items-center gap-2">
            <Plane className="w-4 h-4 text-sky-400" />
            Flight Observations — {selectedRoute} · {selectedWindow}
          </h4>
          <span className="text-xs text-slate-500 font-mono">{flights.length} rows</span>
        </div>

        {loadingFlights ? (
          <div className="flex items-center justify-center gap-2 py-12 text-slate-400 text-sm">
            <Loader2 className="w-5 h-5 animate-spin text-sky-400" />
            Loading observations…
          </div>
        ) : flights.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-slate-500 text-sm gap-2">
            <Database className="w-8 h-8 opacity-30" />
            <span>No observations yet. Press <strong className="text-sky-400">Scrape Now</strong> to fetch data.</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900/90 text-slate-400 uppercase font-semibold text-[10px]">
                <tr>
                  <th className="p-3.5 rounded-l-lg">Airline</th>
                  <th className="p-3.5">Flight</th>
                  <th className="p-3.5">Departure Date</th>
                  <th className="p-3.5">Time</th>
                  <th className="p-3.5">Stops</th>
                  <th className="p-3.5 rounded-r-lg">Total Fare (INR)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-medium">
                {flights.slice(0, 50).map((f) => (
                  <tr key={f.observation_id} className="hover:bg-slate-900/60 transition-colors">
                    <td className="p-3.5 text-slate-200">{f.airline_name}</td>
                    <td className="p-3.5 font-mono text-slate-300">{f.flight_number}</td>
                    <td className="p-3.5 font-mono text-slate-300">{f.departure_date}</td>
                    <td className="p-3.5 font-mono text-slate-400">{f.departure_time || '—'}</td>
                    <td className="p-3.5 text-slate-400 text-center">—</td>
                    <td className="p-3.5 font-mono font-bold text-white">
                      ₹{f.price ? f.price.toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {flights.length > 50 && (
              <div className="px-5 py-3 text-xs text-slate-500 text-center border-t border-slate-800">
                Showing 50 of {flights.length} observations
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
