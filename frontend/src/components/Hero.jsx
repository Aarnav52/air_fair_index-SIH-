import React from 'react';
import { TrendingUp, ArrowDownRight, ArrowUpRight, Sparkles, ChevronDown, BookOpen, Layers, Shield } from 'lucide-react';
import { HERO_STATS } from '../data/mockData';

export default function Hero({ onExploreClick, onWhitepaperClick }) {
  return (
    <section className="relative pt-32 pb-20 overflow-hidden light-hero-bg text-slate-900 border-b border-sky-100">
      
      {/* Background Decorative Mesh & Light Glows */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-gradient-to-tr from-sky-200/40 via-blue-100/30 to-sky-300/20 blur-3xl rounded-full opacity-70"></div>
        <div className="absolute top-0 right-10 w-96 h-96 bg-sky-400/10 rounded-full blur-2xl"></div>
        
        {/* Subtle grid pattern overlay */}
        <div className="absolute inset-0 opacity-[0.04] bg-[radial-gradient(#0284c7_1px,transparent_1px)] [background-size:24px_24px]"></div>
      </div>

      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center">
        
        {/* Top Tag Pill */}
        <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full bg-sky-100/80 border border-sky-200 text-sky-800 text-xs font-bold tracking-wide uppercase shadow-sm mb-6 animate-pulse-slow">
          <Sparkles className="w-3.5 h-3.5 text-sky-600" />
          <span>India Aviation Economics • MoSPI Calibrated</span>
        </div>

        {/* Hero Title */}
        <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-slate-900 tracking-tight leading-[1.15] max-w-4xl mx-auto font-sans">
          The First Real-Time <br className="hidden sm:inline" />
          <span className="text-gradient-hero">Airfare Price Index</span> for India
        </h1>

        {/* Hero Subtitle */}
        <p className="mt-6 text-base sm:text-lg text-slate-600 max-w-3xl mx-auto font-normal leading-relaxed">
          Live benchmark tracking <strong className="text-slate-900 font-semibold">2,500+ real fares</strong> across
          7 domestic routes, 12 airlines, T+1 and T+30 booking windows,
          aggregated via <strong className="text-slate-900 font-semibold">Jevons price relatives</strong> —
          multilateral GEKS aggregation and DGCA traffic-weighting are the next build phase.
        </p>

        {/* 4 Top KPI Metric Cards */}
        <div className="mt-10 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
          {HERO_STATS.map((stat, idx) => (
            <div 
              key={idx} 
              className="light-section-card p-5 rounded-2xl text-left transition-all duration-300 transform hover:-translate-y-1"
            >
              <span className="text-xs font-semibold text-slate-500 block uppercase tracking-wider mb-1">
                {stat.label}
              </span>
              <div className="flex items-baseline justify-between mt-1">
                <span className="text-2xl sm:text-3xl font-extrabold text-slate-900 font-mono tracking-tight">
                  {stat.value}
                </span>
                {stat.change && (
                  <span className={`inline-flex items-center text-xs font-bold px-2 py-0.5 rounded-full ${
                    stat.status === 'up' 
                      ? 'bg-emerald-100 text-emerald-800 border border-emerald-200' 
                      : 'bg-rose-100 text-rose-800 border border-rose-200'
                  }`}>
                    {stat.status === 'up' ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
                    {stat.change}
                  </span>
                )}
              </div>
              <span className="text-[11px] font-medium text-slate-400 mt-2 block font-sans">
                {stat.period || stat.subtext}
              </span>
            </div>
          ))}
        </div>

        {/* Action Buttons */}
        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <button 
            onClick={onExploreClick}
            className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-7 py-3.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-sm shadow-xl shadow-sky-600/30 hover:shadow-sky-500/40 transition-all transform hover:-translate-y-0.5 active:translate-y-0"
          >
            <span>Explore Live Index</span>
            <ChevronDown className="w-4 h-4 animate-bounce" />
          </button>
          
          <button 
            onClick={onWhitepaperClick}
            className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-7 py-3.5 rounded-xl bg-white hover:bg-slate-50 text-slate-800 border border-slate-300 font-bold text-sm shadow-md hover:shadow-lg transition-all"
          >
            <BookOpen className="w-4 h-4 text-sky-600" />
            <span>Whitepaper & Methodology</span>
          </button>
        </div>

        {/* Methodology Sub-strip */}
        <div className="mt-12 pt-6 border-t border-sky-200/60 flex flex-wrap items-center justify-center gap-6 text-xs text-slate-500 font-medium">
          <div className="flex items-center space-x-1.5">
            <Shield className="w-4 h-4 text-sky-600" />
            <span>MoSPI Inflation Aligned</span>
          </div>
          <span className="w-1 h-1 rounded-full bg-slate-300"></span>
          <div className="flex items-center space-x-1.5">
            <Layers className="w-4 h-4 text-sky-600" />
            <span>GEKS Multilateral Transitivity</span>
          </div>
          <span className="w-1 h-1 rounded-full bg-slate-300"></span>
          <div className="flex items-center space-x-1.5">
            <TrendingUp className="w-4 h-4 text-sky-600" />
            <span>Daily Automated Scrapers</span>
          </div>
        </div>

      </div>
    </section>
  );
}
