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
  const [selectedWindow, setSelectedWindow] = useState('T+1');

  // NEW: selected route
  const [selectedRoute, setSelectedRoute] = useState('ALL');

  const [flights, setFlights] = useState([]);
  const [loading, setLoading] = useState(true);

  /*
   * =====================================================
   * FETCH DATA FOR SELECTED BOOKING WINDOW
   * =====================================================
   */
  useEffect(() => {
    setLoading(true);

    console.log(
      `Fetching airline data for ${selectedWindow}`
    );

    fetchFlights('', selectedWindow)
      .then((data) => {
        console.log(
          `Flights received for ${selectedWindow}:`,
          data.length
        );

        console.log(
          `Sample ${selectedWindow} data:`,
          data.slice(0, 3)
        );

        setFlights(data);
      })
      .catch((error) => {
        console.error(
          'Failed to fetch airline data:',
          error
        );

        setFlights([]);
      })
      .finally(() => {
        setLoading(false);
      });
  }, [selectedWindow]);

  const [showIndigo, setShowIndigo] = useState(true);
  const [showAirIndia, setShowAirIndia] = useState(true);
  const [showAkasa, setShowAkasa] = useState(true);
  const [showSpicejet, setShowSpicejet] = useState(true);

  /*
   * =====================================================
   * AVAILABLE ROUTES
   * =====================================================
   *
   * Routes are generated automatically from the flight data.
   *
   * Example:
   *
   * AMD → DEL
   * DEL → BOM
   * DEL → BLR
   *
   * No hard-coded route list is required.
   */
  const availableRoutes = useMemo(() => {
    const routeMap = new Map();

    flights.forEach((flight) => {
      if (!flight.origin || !flight.destination) {
        return;
      }

      const code =
        `${flight.origin}-${flight.destination}`;

      routeMap.set(code, {
        code,
        origin: flight.origin,
        destination: flight.destination
      });
    });

    return Array.from(routeMap.values()).sort(
      (a, b) =>
        a.code.localeCompare(b.code)
    );
  }, [flights]);

  /*
   * Convert UTC timestamp into an Indian calendar date.
   *
   * Example:
   *
   * 2026-09-13T19:59:18+00:00
   *
   * becomes:
   *
   * 2026-09-14
   */
  const getIndiaScrapeDate = (timestamp) => {
    if (!timestamp) return null;

    const date = new Date(timestamp);

    if (Number.isNaN(date.getTime())) {
      return null;
    }

    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    }).formatToParts(date);

    const year = parts.find(
      (part) => part.type === 'year'
    )?.value;

    const month = parts.find(
      (part) => part.type === 'month'
    )?.value;

    const day = parts.find(
      (part) => part.type === 'day'
    )?.value;

    if (!year || !month || !day) {
      return null;
    }

    return `${year}-${month}-${day}`;
  };

  /*
   * Number of days for the dashboard range.
   */
  const getRangeDays = () => {
    switch (timeRange) {
      case '7D':
        return 7;

      case '30D':
        return 30;

      case '90D':
        return 90;

      case '1Y':
        return 365;

      default:
        return 90;
    }
  };

  /*
   * =====================================================
   * AIRLINE PRICE INDEX
   * =====================================================
   *
   * Pipeline:
   *
   * Database/API observations
   *          ↓
   * selected booking window
   *          ↓
   * selected route
   *          ↓
   * scrape_timestamp
   *          ↓
   * IST scrape date
   *          ↓
   * airline + scrape date
   *          ↓
   * average fare
   *          ↓
   * base fare = 100
   *          ↓
   * price index
   */
  const airlineData = useMemo(() => {
    if (!flights.length) {
      return [];
    }

    // --------------------------------------------------
    // 1. Select booking window + route
    // --------------------------------------------------

    const selectedFlights = flights.filter(
      (flight) =>
        flight.window === selectedWindow &&
        flight.scrape_timestamp &&
        typeof flight.price === 'number' &&
        flight.price > 0 &&
        (
          selectedRoute === 'ALL' ||
          `${flight.origin}-${flight.destination}` ===
            selectedRoute
        )
    );

    if (!selectedFlights.length) {
      return [];
    }

    // --------------------------------------------------
    // 2. Attach IST scrape date
    // --------------------------------------------------

    const observations = selectedFlights
      .map((flight) => ({
        ...flight,
        indiaScrapeDate:
          getIndiaScrapeDate(
            flight.scrape_timestamp
          )
      }))
      .filter(
        (flight) =>
          flight.indiaScrapeDate !== null
      );

    if (!observations.length) {
      return [];
    }

    // --------------------------------------------------
    // 3. Find all scrape dates
    // --------------------------------------------------

    const allDates = [
      ...new Set(
        observations.map(
          (flight) =>
            flight.indiaScrapeDate
        )
      )
    ].sort();

    if (!allDates.length) {
      return [];
    }

    // --------------------------------------------------
    // 4. Apply time range
    // --------------------------------------------------

    const latestDate = new Date(
      `${allDates[allDates.length - 1]}T00:00:00`
    );

    const earliestDate = new Date(
      latestDate
    );

    earliestDate.setDate(
      earliestDate.getDate() -
        (getRangeDays() - 1)
    );

    const rangeFilteredFlights =
      observations.filter((flight) => {

        const date = new Date(
          `${flight.indiaScrapeDate}T00:00:00`
        );

        return (
          date >= earliestDate &&
          date <= latestDate
        );
      });

    if (!rangeFilteredFlights.length) {
      return [];
    }

    // --------------------------------------------------
    // 5. Group by:
    //
    // scrape date
    //      +
    // airline
    // --------------------------------------------------

    const grouped = {};

    rangeFilteredFlights.forEach(
      (flight) => {

        const date =
          flight.indiaScrapeDate;

        const airline =
          flight.airline_name;

        if (!grouped[date]) {
          grouped[date] = {};
        }

        if (!grouped[date][airline]) {
          grouped[date][airline] = {
            total: 0,
            count: 0
          };
        }

        grouped[date][airline].total +=
          flight.price;

        grouped[date][airline].count += 1;
      }
    );

    const dates =
      Object.keys(grouped).sort();

    if (!dates.length) {
      return [];
    }

    // --------------------------------------------------
    // 6. Calculate BASE PRICE for each airline
    //
    // The first date on which an airline has valid
    // observations becomes that airline's base.
    // --------------------------------------------------

    const basePrices = {};

    for (const date of dates) {

      for (
        const [airline, values]
        of Object.entries(grouped[date])
      ) {

        if (
          basePrices[airline] === undefined &&
          values.count > 0
        ) {
          basePrices[airline] =
            values.total /
            values.count;
        }
      }
    }

    // --------------------------------------------------
    // 7. Convert average fare → index
    // --------------------------------------------------

    const result = dates.map(
      (date) => {

        const point = {

          // Raw date internally.
          scrapeDate: date,

          // Display date.
          date: new Date(
            `${date}T00:00:00`
          ).toLocaleDateString(
            'en-IN',
            {
              timeZone: 'Asia/Kolkata',
              day: 'numeric',
              month: 'short'
            }
          )
        };

        Object.entries(
          grouped[date]
        ).forEach(
          ([airline, values]) => {

            if (!values.count) {
              return;
            }

            const averageFare =
              values.total /
              values.count;

            const baseFare =
              basePrices[airline];

            if (
              !baseFare ||
              baseFare <= 0 ||
              averageFare <= 0
            ) {
              return;
            }

            const index =
              (averageFare /
                baseFare) *
              100;

            const change =
              index - 100;

            point[airline] =
              Number(
                index.toFixed(2)
              );

            point[
              `${airline}_price`
            ] =
              Number(
                averageFare.toFixed(2)
              );

            point[
              `${airline}_change`
            ] =
              Number(
                change.toFixed(2)
              );
          }
        );

        return point;
      }
    );

    console.log(
      `Airline data - ${selectedRoute} - ${selectedWindow}:`,
      result
    );

    return result;

  }, [
    flights,
    selectedWindow,
    selectedRoute,
    timeRange
  ]);

  /*
   * =====================================================
   * AIRLINE SUMMARY
   * =====================================================
   *
   * Summary now respects the selected route too.
   */
  const airlineSummary = useMemo(() => {

    const summary = {};

    flights
      .filter(
        (flight) =>
          flight.window ===
            selectedWindow &&
          (
            selectedRoute === 'ALL' ||
            `${flight.origin}-${flight.destination}` ===
              selectedRoute
          ) &&
          typeof flight.price === 'number' &&
          flight.price > 0
      )
      .forEach((flight) => {

        const airline =
          flight.airline_name;

        if (!summary[airline]) {
          summary[airline] = {
            total: 0,
            count: 0
          };
        }

        summary[airline].total +=
          flight.price;

        summary[airline].count +=
          1;
      });

    return Object.entries(summary)
      .map(
        ([airline, values]) => ({
          airline,

          averageFare:
            values.count
              ? Number(
                  (
                    values.total /
                    values.count
                  ).toFixed(2)
                )
              : 0,

          count: values.count
        })
      );

  }, [
    flights,
    selectedWindow,
    selectedRoute
  ]);

  return (
    <div className="space-y-8">

      {/* =================================================
          HEADER
      ================================================= */}

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

        {/* SELECTORS */}

        <div className="flex flex-wrap items-center gap-3 self-start sm:self-auto">

          {/* ROUTE SELECTOR */}

          <div className="flex items-center gap-2">

            <span className="text-xs text-slate-400 font-semibold">

              Route

            </span>

            <select
              value={selectedRoute}
              onChange={(e) =>
                setSelectedRoute(
                  e.target.value
                )
              }
              className="bg-slate-900 border border-slate-800 text-white text-xs font-semibold rounded-xl px-3 py-2 outline-none focus:border-sky-500"
            >

              <option value="ALL">
                All Routes
              </option>

              {availableRoutes.map(
                (route) => (

                  <option
                    key={route.code}
                    value={route.code}
                  >
                    {route.origin} → {route.destination}
                  </option>

                )
              )}

            </select>

          </div>

          {/* BOOKING WINDOW */}

          <div className="flex items-center gap-2">

            <span className="text-xs text-slate-400 font-semibold">

              Booking Window

            </span>

            <div className="flex bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs font-semibold">

              {[
                'T+1',
                'T+30'
              ].map(
                (window) => (

                  <button
                    key={window}
                    onClick={() =>
                      setSelectedWindow(
                        window
                      )
                    }
                    className={`px-3 py-1.5 rounded-lg transition-all ${
                      selectedWindow ===
                      window
                        ? 'bg-sky-500 text-white shadow-md'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >

                    {window}

                  </button>

                )
              )}

            </div>

          </div>

          {/* TIME RANGE */}

          <div className="flex bg-slate-900 p-1 rounded-xl border border-slate-800 text-xs font-semibold">

            {[
              '7D',
              '30D',
              '90D',
              '1Y'
            ].map(
              (range) => (

                <button
                  key={range}
                  onClick={() =>
                    setTimeRange(
                      range
                    )
                  }
                  className={`px-3 py-1.5 rounded-lg transition-all ${
                    timeRange === range
                      ? 'bg-sky-500 text-white shadow-md'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >

                  {range}

                </button>

              )
            )}

          </div>

        </div>

      </div>

      {/* =================================================
          CHART
      ================================================= */}

      <div className="glass-panel p-6 rounded-3xl space-y-6">

        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">

          <div>

            <h4 className="text-base font-bold text-white flex items-center gap-2">

              <BarChart2 className="w-4 h-4 text-sky-400" />

              Airline Price Index Trajectory (
              {selectedRoute === 'ALL'
                ? 'All Routes'
                : selectedRoute.replace(
                    '-',
                    ' → '
                  )}
              {' • '}
              {selectedWindow} • {timeRange}
              )

            </h4>

            <p className="text-xs text-slate-400">

              Based on scrape date in IST • First valid observation for each airline = 100

            </p>

          </div>

          {/* AIRLINE TOGGLES */}

          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">

            <button
              onClick={() =>
                setShowIndigo(
                  !showIndigo
                )
              }
              className={`px-3 py-1.5 rounded-lg border transition-all ${
                showIndigo
                  ? 'bg-blue-500/20 text-blue-300 border-blue-500/40'
                  : 'bg-slate-900 text-slate-500 border-slate-800 line-through'
              }`}
            >
              IndiGo
            </button>

            <button
              onClick={() =>
                setShowAirIndia(
                  !showAirIndia
                )
              }
              className={`px-3 py-1.5 rounded-lg border transition-all ${
                showAirIndia
                  ? 'bg-rose-500/20 text-rose-300 border-rose-500/40'
                  : 'bg-slate-900 text-slate-500 border-slate-800 line-through'
              }`}
            >
              Air India
            </button>

            <button
              onClick={() =>
                setShowAkasa(
                  !showAkasa
                )
              }
              className={`px-3 py-1.5 rounded-lg border transition-all ${
                showAkasa
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                  : 'bg-slate-900 text-slate-500 border-slate-800 line-through'
              }`}
            >
              Akasa Air
            </button>

            <button
              onClick={() =>
                setShowSpicejet(
                  !showSpicejet
                )
              }
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

        {/* LOADING */}

        {loading && (
          <div className="h-80 flex items-center justify-center text-slate-400">

            Loading airline data...

          </div>
        )}

        {/* EMPTY */}

        {!loading &&
          airlineData.length === 0 && (

            <div className="h-80 flex items-center justify-center text-slate-400">

              No airline observations available for{' '}
              {selectedRoute === 'ALL'
                ? 'all routes'
                : selectedRoute.replace(
                    '-',
                    ' → '
                  )}{' '}
              ({selectedWindow}).

            </div>

          )}

        {/* CHART */}

        {!loading &&
          airlineData.length > 0 && (

            <div className="w-full h-80 sm:h-96 pt-4">

              <ResponsiveContainer
                width="100%"
                height="100%"
              >

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
                    domain={[
                      'dataMin - 5',
                      'dataMax + 5'
                    ]}
                    label={{
                      value:
                        'Airfare Price Index',
                      angle: -90,
                      position:
                        'insideLeft',
                      fill: '#64748b',
                      fontSize: 11
                    }}
                  />

                  <Tooltip
                    contentStyle={{
                      backgroundColor:
                        '#090d16',
                      borderColor:
                        '#38bdf833',
                      borderRadius:
                        '12px',
                      boxShadow:
                        '0 10px 25px rgba(0,0,0,0.8)',
                      color: '#fff',
                      fontSize:
                        '12px'
                    }}

                    formatter={(
                      value,
                      name,
                      props
                    ) => {

                      const price =
                        props.payload[
                          `${name}_price`
                        ];

                      const change =
                        props.payload[
                          `${name}_change`
                        ];

                      return [
                        `Index: ${value} | ₹${price} | ${
                          change >= 0
                            ? '+'
                            : ''
                        }${change}%`,
                        name
                      ];

                    }}
                  />

                  <Legend
                    wrapperStyle={{
                      fontSize: '11px',
                      paddingTop:
                        '10px'
                    }}
                  />

                  {showIndigo && (
                    <Line
                      type="monotone"
                      dataKey="IndiGo"
                      name="IndiGo"
                      stroke="#38bdf8"
                      strokeWidth={2.5}
                      dot={true}
                      connectNulls={true}
                    />
                  )}

                  {showAirIndia && (
                    <Line
                      type="monotone"
                      dataKey="Air India"
                      name="Air India"
                      stroke="#f43f5e"
                      strokeWidth={2.5}
                      dot={true}
                      connectNulls={true}
                    />
                  )}

                  {showAkasa && (
                    <Line
                      type="monotone"
                      dataKey="Akasa Air"
                      name="Akasa Air"
                      stroke="#f59e0b"
                      strokeWidth={2.5}
                      dot={true}
                      connectNulls={true}
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
                      dot={true}
                      connectNulls={true}
                    />
                  )}

                </LineChart>

              </ResponsiveContainer>

            </div>

          )}

      </div>

      {/* =================================================
          SUMMARY
      ================================================= */}

      <div className="glass-panel p-6 rounded-3xl space-y-4">

        <div>

          <h4 className="text-base font-bold text-white flex items-center gap-2">

            <Layers className="w-4 h-4 text-sky-400" />

            Airline Observation Summary (
            {selectedRoute === 'ALL'
              ? 'All Routes'
              : selectedRoute.replace(
                  '-',
                  ' → '
                )}
            {' • '}
            {selectedWindow}
            )

          </h4>

          <p className="text-xs text-slate-400">

            Average fares and observation counts for the selected route and booking window.

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

              {airlineSummary.map(
                (item) => (

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

                )
              )}

            </tbody>

          </table>

        </div>

        <div className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">

          <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />

          <span>

            Index values are calculated from real flight observations. The current base is the first valid observation for each airline in the selected route and booking window.

          </span>

        </div>

      </div>

    </div>
  );
}