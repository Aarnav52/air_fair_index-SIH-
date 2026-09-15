import React, { useState, useMemo, useEffect } from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend
} from 'recharts';
import { Plane, BarChart2, Layers, ShieldCheck } from 'lucide-react';
import { fetchFlights } from '../api/apiService';

export default function AirlineAnalytics() {
  const [timeRange, setTimeRange] = useState('90D');

  const [flights, setFlights] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchFlights()
      .then((data) => {
        setFlights(data);
      })
      .catch((error) => {
        console.error('Failed to fetch airline data:', error);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  // Carrier toggles
  const [showIndigo, setShowIndigo] = useState(true);
  const [showAirIndia, setShowAirIndia] = useState(true);
  const [showAkasa, setShowAkasa] = useState(true);
  const [showSpicejet, setShowSpicejet] = useState(true);

  // Create airline-wise price index data
  const airlineData = useMemo(() => {
    if (!flights.length) return [];

    const grouped = {};

    // Group observations by departure date and airline
    flights.forEach((flight) => {
      const date = flight.departure_date;
      const airline = flight.airline_name;

      if (!grouped[date]) {
        grouped[date] = {};
      }

      if (!grouped[date][airline]) {
        grouped[date][airline] = {
          total: 0,
          count: 0,
        };
      }

      grouped[date][airline].total += flight.price;
      grouped[date][airline].count += 1;
    });

    const dates = Object.keys(grouped).sort();

    if (!dates.length) return [];

    // Earliest available observation is temporary base = 100
    const basePrices = {};
    const baseDate = dates[0];

    Object.entries(grouped[baseDate]).forEach(([airline, values]) => {
      basePrices[airline] = values.total / values.count;
    });

    // Convert prices into index values
    return dates.map((date) => {
      const point = {
        date: new Date(date).toLocaleDateString('en-IN', {
          month: 'short',
          day: 'numeric',
        }),
      };

      Object.entries(grouped[date]).forEach(([airline, values]) => {
        const averageFare = values.total / values.count;
        const baseFare = basePrices[airline];

        if (baseFare > 0) {
          const index = (averageFare / baseFare) * 100;
          const changePercent = index - 100;

          point[airline] = Number(index.toFixed(2));
          point[`${airline}_price`] = Number(averageFare.toFixed(2));
          point[`${airline}_change`] = Number(changePercent.toFixed(2));
        }
      });

      return point;
    });
  }, [flights]);

  // Calculate current average fare for each airline
  const airlineSummary = useMemo(() => {
    const summary = {};

    flights.forEach((flight) => {
      const airline = flight.airline_name;

      if (!summary[airline]) {
        summary[airline] = {
          total: 0,
          count: 0,
        };
      }

      summary[airline].total += flight.price;
      summary[airline].count += 1;
    });

    return Object.entries(summary).map(([airline, values]) => ({
      airline,
      averageFare: values.count
        ? Number((values.total / values.count).toFixed(2))
        : 0,
      count: values.count,
    }));
  }, [flights]);

  return (
    <div className="space-y-8">

      {/* Top Banner Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <span className="p-1.5 rounded-lg bg-sky-500/10 text-sky-400 border border-sky-500/30">
              <Plane className="w-4 h-4" />
            </span>

            <h3 className="text-xl font-extrabold text-white font-sans">
              Airline-Wise Airfare Price Index
            </h3>
          </div>

          <p className="text-xs text-slate-400 mt-1">
            Airline-wise price movement calculated from real flight observations.
          </p>
        </div>

        {/* Time Range Selector */}
        <div className="flex bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs font-semibold self-start sm:self-auto">
          {['7D', '30D', '90D', '1Y'].map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1.5 rounded-lg transition-all ${
                timeRange === range
                  ? 'bg-sky-500 text-white shadow-md'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* CHART MODULE */}
      <div className="glass-panel p-6 rounded-3xl space-y-6">

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">

          <div>
            <h4 className="text-base font-bold text-white flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-sky-400" />
              Airline Price Index Trajectory ({timeRange})
            </h4>

            <p className="text-xs text-slate-400">
              Earliest available observation = 100 • Hover to view fare and percentage movement
            </p>
          </div>

          {/* Carrier Visibility Toggles */}
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">

            <button
              onClick={() => setShowIndigo(!showIndigo)}
              className={`px-3 py-1.5 rounded-lg border transition-all ${
                showIndigo
                  ? 'bg-blue-500/20 text-blue-300 border-blue-500/40'
                  : 'bg-slate-900 text-slate-500 border-slate-800 line-through'
              }`}
            >
              IndiGo
            </button>

            <button
              onClick={() => setShowAirIndia(!showAirIndia)}
              className={`px-3 py-1.5 rounded-lg border transition-all ${
                showAirIndia
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                  : 'bg-slate-900 text-slate-500 border-slate-800 line-through'
              }`}
            >
              Air India
            </button>

            <button
              onClick={() => setShowAkasa(!showAkasa)}
              className={`px-3 py-1.5 rounded-lg border transition-all ${
                showAkasa
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                  : 'bg-slate-900 text-slate-500 border-slate-800 line-through'
              }`}
            >
              Akasa Air
            </button>

            <button
              onClick={() => setShowSpicejet(!showSpicejet)}
              className={`px-3 py-1.5 rounded-lg border transition-all ${
                showSpicejet
                  ? 'bg-yellow-500/20 text-yellow-300 border-yellow-500/40'
                  : 'bg-slate-900 text-slate-500 border-slate-800 line-through'
              }`}
            >
              SpiceJet
            </button>

          </div>
        </div>

        {/* Loading */}
        {loading && (
          <div className="h-80 flex items-center justify-center text-slate-400">
            Loading airline data...
          </div>
        )}

        {/* Empty */}
        {!loading && airlineData.length === 0 && (
          <div className="h-80 flex items-center justify-center text-slate-400">
            No airline observations available.
          </div>
        )}

        {/* Chart */}
        {!loading && airlineData.length > 0 && (
          <div className="w-full h-80 sm:h-96 pt-4">

            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={airlineData}
                margin={{
                  top: 10,
                  right: 10,
                  left: -20,
                  bottom: 0
                }}
              >

                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke="#1e293b"
                />

                <XAxis
                  dataKey="date"
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                />

                <YAxis
                  stroke="#64748b"
                  fontSize={11}
                  tickLine={false}
                  domain={['dataMin - 5', 'dataMax + 5']}
                  label={{
                    value: 'Airfare Price Index',
                    angle: -90,
                    position: 'insideLeft',
                    fill: '#64748b',
                    fontSize: 11
                  }}
                />

                <Tooltip
                  contentStyle={{
                    backgroundColor: '#090d16',
                    borderColor: '#38bdf833',
                    borderRadius: '12px',
                    boxShadow: '0 10px 25px rgba(0,0,0,0.8)',
                    color: '#fff',
                    fontSize: '12px'
                  }}
                  formatter={(value, name, props) => {

                    const priceKey = `${name}_price`;
                    const changeKey = `${name}_change`;

                    const price = props.payload[priceKey];
                    const change = props.payload[changeKey];

                    return [
                      `Index: ${value} | ₹${price} | ${
                        change >= 0 ? '+' : ''
                      }${change}%`,
                      name
                    ];
                  }}
                />

                <Legend
                  wrapperStyle={{
                    fontSize: '11px',
                    paddingTop: '10px'
                  }}
                />

                {showIndigo && (
                  <Line
                    type="monotone"
                    dataKey="IndiGo"
                    name="IndiGo"
                    stroke="#38bdf8"
                    strokeWidth={2.5}
                    dot={false}
                  />
                )}

                {showAirIndia && (
                  <Line
                    type="monotone"
                    dataKey="Air India"
                    name="Air India"
                    stroke="#f43f5e"
                    strokeWidth={2.5}
                    dot={false}
                  />
                )}

                {showAkasa && (
                  <Line
                    type="monotone"
                    dataKey="Akasa Air"
                    name="Akasa Air"
                    stroke="#f59e0b"
                    strokeWidth={2.5}
                    dot={false}
                  />
                )}

                {showSpicejet && (
                  <Line
                    type="monotone"
                    dataKey="SpiceJet"
                    name="SpiceJet"
                    stroke="#eab308"
                    strokeWidth={2}
                    strokeDasharray="4 4"
                    dot={false}
                  />
                )}

              </LineChart>
            </ResponsiveContainer>

          </div>
        )}

      </div>

      {/* REAL DATA SUMMARY */}
      <div className="glass-panel p-6 rounded-3xl space-y-4">

        <div>
          <h4 className="text-base font-bold text-white flex items-center gap-2">
            <Layers className="w-4 h-4 text-sky-400" />
            Airline Observation Summary
          </h4>

          <p className="text-xs text-slate-400">
            Average fares and observation counts calculated directly from backend data.
          </p>
        </div>

        <div className="overflow-x-auto">

          <table className="w-full text-left text-xs">

            <thead className="bg-slate-900/90 text-slate-400 uppercase font-semibold text-[10px]">

              <tr>
                <th className="p-3.5 rounded-l-lg">
                  Airline Carrier
                </th>

                <th className="p-3.5">
                  Average Fare
                </th>

                <th className="p-3.5">
                  Observations
                </th>

                <th className="p-3.5 rounded-r-lg">
                  Data Source
                </th>
              </tr>

            </thead>

            <tbody className="divide-y divide-slate-800/60 font-medium">

              {airlineSummary.map((item) => (

                <tr
                  key={item.airline}
                  className="hover:bg-slate-900/60 transition-colors"
                >

                  <td className="p-3.5 font-bold text-white">
                    {item.airline}
                  </td>

                  <td className="p-3.5 font-mono text-sky-400 font-bold">
                    ₹{item.averageFare}
                  </td>

                  <td className="p-3.5 font-mono text-slate-300">
                    {item.count}
                  </td>

                  <td className="p-3.5">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                      Backend / PostgreSQL
                    </span>
                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">

          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />

          <span>
            Index values are calculated from real flight observations. The current base is the earliest available observation.
          </span>

        </div>

      </div>

    </div>
  );
}