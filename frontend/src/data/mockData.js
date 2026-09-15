// APEX-IND Simulated Real-Time Data Engine for Airfare Price Index & Analytics

// Real, verifiable operational counts (live DB, apix(SIH)) — not derived
// index statistics, since GEKS-Jevons aggregation isn't wired to the live
// API yet. Update these if the live counts change materially.
export const HERO_STATS = [
  { label: 'Real Fare Observations', value: '2,574', subtext: '100% real_scraped, zero synthetic', status: 'neutral' },
  { label: 'Active Routes', value: '7', subtext: 'DEL-BOM, DEL-BLR, BOM-BLR + 4 more', status: 'neutral' },
  { label: 'Airlines Tracked', value: '12', subtext: 'via SerpApi + direct Akasa/SpiceJet', status: 'neutral' },
  { label: 'Booking Windows', value: 'T+1 · T+30', subtext: 'every 6h / daily, automated', status: 'neutral' }
];

export const LIVE_TICKER_FEED = [
  { id: 1, route: 'DEL → BOM', airline: 'IndiGo', code: '6E-2041', rawFare: 5240, cleanFare: 4850, change: '+2.1%', status: 'Normal', time: '12s ago' },
  { id: 2, route: 'BOM → BLR', airline: 'Air India', code: 'AI-609', rawFare: 4100, cleanFare: 3420, change: '-1.2%', status: 'Cleaned', time: '18s ago' },
  { id: 3, route: 'DEL → CCU', airline: 'Vistara', code: 'UK-707', rawFare: 5890, cleanFare: 5100, change: '+0.5%', status: 'Normal', time: '34s ago' },
  { id: 4, route: 'BLR → DEL', airline: 'Akasa Air', code: 'QP-1102', rawFare: 6950, cleanFare: 6200, change: '+3.4%', status: 'Promo Filtered', time: '42s ago' },
  { id: 5, route: 'HYD → BOM', airline: 'SpiceJet', code: 'SG-432', rawFare: 4300, cleanFare: 3890, change: '-0.8%', status: 'Normal', time: '55s ago' },
  { id: 6, route: 'MAA → DEL', airline: 'IndiGo', code: '6E-512', rawFare: 6100, cleanFare: 5650, change: '+1.9%', status: 'Cleaned', time: '1m ago' },
];

export const BOOKING_WINDOWS = [
  { bucket: 'T-0 (Same Day)', avgPrice: 9450, indexWeight: '12%', volatility: '0.082', trend: '+4.8%', multiplier: '1.44x' },
  { bucket: 'T-3 (1-3 Days)', avgPrice: 7800, indexWeight: '22%', volatility: '0.054', trend: '+2.1%', multiplier: '1.22x' },
  { bucket: 'T-7 (4-7 Days)', avgPrice: 6150, indexWeight: '28%', volatility: '0.038', trend: '+1.2%', multiplier: '1.00x' },
  { bucket: 'T-14 (8-14 Days)', avgPrice: 5100, indexWeight: '18%', volatility: '0.024', trend: '-0.4%', multiplier: '0.85x' },
  { bucket: 'T-30 (15-30 Days)', avgPrice: 4350, indexWeight: '12%', volatility: '0.019', trend: '-1.1%', multiplier: '0.72x' },
  { bucket: 'T-45 (31-45 Days)', avgPrice: 3950, indexWeight: '8%', volatility: '0.015', trend: '-0.2%', multiplier: '0.65x' },
];

export const DEDUPLICATION_STATS = {
  rawScrapedCount: '4,218,940 Fares/Day',
  cleanIndexedCount: '3,619,849 Clean Fares',
  ancillaryFilteredPercent: '14.2%',
  ghostInventoriesRemoved: '99.8%',
  duplicateFaresMerged: '599,091'
};

// Overall Composite Time Series
export const generateTimeSeriesData = (range = '90D', shockFactor = 1.0) => {
  const pointsCount = range === '7D' ? 7 : range === '30D' ? 30 : range === '90D' ? 90 : range === '1Y' ? 365 : 180;
  const data = [];
  let baseGEKS = 152.0 * shockFactor;
  let baseCPI = 148.5;
  let baseATF = 140.0;
  
  const today = new Date();
  
  for (let i = pointsCount; i >= 0; i--) {
    const d = new Date();
    d.setDate(today.getDate() - i);
    
    const randomNoise = (Math.random() - 0.48) * 0.9 * shockFactor;
    const macroTrend = 0.15;
    
    baseGEKS += macroTrend + randomNoise;
    baseCPI += 0.08 + (Math.random() - 0.49) * 0.2;
    baseATF += (Math.random() - 0.45) * 1.2;
    
    data.push({
      date: d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
      fullDate: d.toISOString().split('T')[0],
      geksIndex: parseFloat(baseGEKS.toFixed(2)),
      mospiCPI: parseFloat(baseCPI.toFixed(2)),
      atfBenchmark: parseFloat(baseATF.toFixed(2)),
      avgFare: Math.round(baseGEKS * 32.1),
      volatility: parseFloat((0.035 + Math.random() * 0.01).toFixed(4))
    });
  }
  return data;
};

// Airline-Wise Time Series Data Generator
export const generateAirlineTimeSeriesData = (range = '90D') => {
  const pointsCount = range === '7D' ? 7 : range === '30D' ? 30 : range === '90D' ? 90 : range === '1Y' ? 365 : 180;
  const data = [];
  
  let indigoIdx = 162.0;
  let airIndiaIdx = 168.0;
  let akasaIdx = 155.0;
  let spicejetIdx = 160.0;
  
  const today = new Date();
  
  for (let i = pointsCount; i >= 0; i--) {
    const d = new Date();
    d.setDate(today.getDate() - i);
    
    indigoIdx += 0.12 + (Math.random() - 0.47) * 0.8;
    airIndiaIdx += 0.15 + (Math.random() - 0.45) * 0.9;
    akasaIdx += 0.08 + (Math.random() - 0.50) * 0.7;
    spicejetIdx += 0.05 + (Math.random() - 0.48) * 1.1;
    
    data.push({
      date: d.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }),
      Indigo: parseFloat(indigoIdx.toFixed(2)),
      AirIndia: parseFloat(airIndiaIdx.toFixed(2)),
      AkasaAir: parseFloat(akasaIdx.toFixed(2)),
      SpiceJet: parseFloat(spicejetIdx.toFixed(2))
    });
  }
  return data;
};

// Airline-Weighted Breakdown Table Data
export const AIRLINE_WEIGHTED_TABLE = [
  { 
    id: 1, 
    name: 'IndiGo (6E)', 
    code: '6E', 
    weight: 0.614, 
    weightPercent: '61.4%', 
    baseIndex: 166.8, 
    weightedPoints: (0.614 * 166.8).toFixed(2), 
    shift7d: '+1.2%', 
    shift30d: '+3.4%', 
    activeFleet: 360, 
    category: 'Ultra-LCC' 
  },
  { 
    id: 2, 
    name: 'Air India Group (AI + UK)', 
    code: 'AI/UK', 
    weight: 0.282, 
    weightPercent: '28.2%', 
    baseIndex: 172.4, 
    weightedPoints: (0.282 * 172.4).toFixed(2), 
    shift7d: '+2.1%', 
    shift30d: '+4.8%', 
    activeFleet: 220, 
    category: 'Premium FSC' 
  },
  { 
    id: 3, 
    name: 'Akasa Air (QP)', 
    code: 'QP', 
    weight: 0.048, 
    weightPercent: '4.8%', 
    baseIndex: 159.2, 
    weightedPoints: (0.048 * 159.2).toFixed(2), 
    shift7d: '-0.5%', 
    shift30d: '-1.1%', 
    activeFleet: 24, 
    category: 'Value LCC' 
  },
  { 
    id: 4, 
    name: 'SpiceJet (SG)', 
    code: 'SG', 
    weight: 0.041, 
    weightPercent: '4.1%', 
    baseIndex: 164.1, 
    weightedPoints: (0.041 * 164.1).toFixed(2), 
    shift7d: '+0.0%', 
    shift30d: '+0.8%', 
    activeFleet: 28, 
    category: 'Regional LCC' 
  },
  { 
    id: 5, 
    name: 'AI Express & Alliance Air', 
    code: 'IX/9I', 
    weight: 0.015, 
    weightPercent: '1.5%', 
    baseIndex: 161.0, 
    weightedPoints: (0.015 * 161.0).toFixed(2), 
    shift7d: '+0.2%', 
    shift30d: '+0.5%', 
    activeFleet: 18, 
    category: 'UDAN Regional' 
  }
];

export const TOP_ROUTES_DATA = [
  { rank: 1, route: 'DEL - BOM', name: 'Delhi ↔ Mumbai', volume: '18.4%', avgFare: 5420, change7d: '+2.4%', status: 'High Demand' },
  { rank: 2, route: 'BOM - BLR', name: 'Mumbai ↔ Bengaluru', volume: '14.2%', avgFare: 4150, change7d: '-0.9%', status: 'Stable' },
  { rank: 3, route: 'DEL - BLR', name: 'Delhi ↔ Bengaluru', volume: '12.8%', avgFare: 6890, change7d: '+3.1%', status: 'High Demand' },
  { rank: 4, route: 'DEL - CCU', name: 'Delhi ↔ Kolkata', volume: '9.6%', avgFare: 5210, change7d: '+0.4%', status: 'Stable' },
  { rank: 5, route: 'HYD - BOM', name: 'Hyderabad ↔ Mumbai', volume: '8.1%', avgFare: 3950, change7d: '-1.4%', status: 'Discounted' },
  { rank: 6, route: 'MAA - DEL', name: 'Chennai ↔ Delhi', volume: '7.5%', avgFare: 5980, change7d: '+1.8%', status: 'Stable' },
];

export const AIRLINE_BREAKDOWN = [
  { name: 'IndiGo', code: '6E', marketShare: '61.4%', indexValue: 166.2, change7d: '+1.1%', fleetActive: 360 },
  { name: 'Air India Group (incl. Vistara)', code: 'AI/UK', marketShare: '28.2%', indexValue: 172.8, change7d: '+1.9%', fleetActive: 220 },
  { name: 'Akasa Air', code: 'QP', marketShare: '4.8%', indexValue: 159.4, change7d: '-0.5%', fleetActive: 24 },
  { name: 'SpiceJet', code: 'SG', marketShare: '4.1%', indexValue: 164.1, change7d: '+0.2%', fleetActive: 28 },
  { name: 'Others (Alliance, AIX)', code: 'OTH', marketShare: '1.5%', indexValue: 161.0, change7d: '+0.0%', fleetActive: 18 }
];

export const LIVE_MONITORED_CORRIDORS = [
  { id: 1, route: 'DEL → BOM', carrier: 'IndiGo 6E-2041', horizon: 'T+1 (Tomorrow)', baseFare: 5400, taxes: 1440, totalFare: 6840, vs30d: '+14.2%', status: 'HIGH SURGE', statusStyle: 'bg-rose-500/10 text-rose-400 border-rose-500/30' },
  { id: 2, route: 'DEL → BOM', carrier: 'Air India AI-806', horizon: 'T+7 (1 Week)', baseFare: 4200, taxes: 1220, totalFare: 5420, vs30d: '+1.8%', status: 'STABLE', statusStyle: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  { id: 3, route: 'BOM → BLR', carrier: 'Akasa QP-1311', horizon: 'T+15 (Mid)', baseFare: 3200, taxes: 920, totalFare: 4120, vs30d: '-4.6%', status: 'DISCOUNT', statusStyle: 'bg-blue-500/10 text-blue-400 border-blue-500/30' },
  { id: 4, route: 'DEL → BLR', carrier: 'IndiGo 6E-5012', horizon: 'T+7 (1 Week)', baseFare: 4800, taxes: 1350, totalFare: 6150, vs30d: '+3.2%', status: 'NORMAL', statusStyle: 'bg-sky-500/10 text-sky-400 border-sky-500/30' },
  { id: 5, route: 'BLR → CCU', carrier: 'Air India Express IX-982', horizon: 'T+30 (Monthly)', baseFare: 3800, taxes: 1050, totalFare: 4850, vs30d: '-11.4%', status: 'DISCOUNT', statusStyle: 'bg-blue-500/10 text-blue-400 border-blue-500/30' },
  { id: 6, route: 'DEL → HYD', carrier: 'SpiceJet SG-8169', horizon: 'T+1 (Tomorrow)', baseFare: 6200, taxes: 1500, totalFare: 7700, vs30d: '+22.1%', status: 'CRITICAL', statusStyle: 'bg-rose-600/20 text-rose-300 border-rose-500/40 font-bold' },
  { id: 7, route: 'BOM → GOI', carrier: 'IndiGo 6E-442', horizon: 'T+7 (Weekend)', baseFare: 3400, taxes: 890, totalFare: 4290, vs30d: '+8.4%', status: 'LEISURE SURGE', statusStyle: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
  { id: 8, route: 'CCU → GAU', carrier: 'Air India AI-721', horizon: 'T+15 (UDAN Hub)', baseFare: 2600, taxes: 620, totalFare: 3220, vs30d: '-1.2%', status: 'UDAN CAPPED', statusStyle: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' },
  { id: 9, route: 'DEL → PNQ', carrier: 'Air India AI-849', horizon: 'T+7 (1 Week)', baseFare: 4100, taxes: 1180, totalFare: 5280, vs30d: '+2.4%', status: 'NORMAL', statusStyle: 'bg-sky-500/10 text-sky-400 border-sky-500/30' },
  { id: 10, route: 'BOM → COK', carrier: 'Akasa QP-1522', horizon: 'T+45 (Advance)', baseFare: 2900, taxes: 840, totalFare: 3740, vs30d: '-18.2%', status: 'EARLY BIRD', statusStyle: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' }
];

export const GOVERNANCE_STATS = {
  transitivityScore: '1.0000 (Pass)',
  missingQuoteImputation: 'Hedonic Regression',
  routeBreadth: '94.8% Seat Capacity',
  outlierRejectionRate: '0.24% of quotes',
  updateFrequency: 'Every 15 Minutes'
};

export const SIMULATION_PRESETS = [
  { id: 'normal', label: 'Baseline Market', shockFactor: 1.0, desc: 'Normal domestic aviation supply and demand.' },
  { id: 'diwali', label: 'Festive Surge (+18%)', shockFactor: 1.18, desc: 'Diwali & festival demand surge across trunk corridors.' },
  { id: 'monsoon', label: 'Monsoon Discount (-12%)', shockFactor: 0.88, desc: 'Seasonal off-peak pricing across regional routes.' },
  { id: 'fuel_spike', label: 'ATF Fuel Spike (+24%)', shockFactor: 1.24, desc: 'Crude price escalation pushing airline fuel surcharges.' }
];
