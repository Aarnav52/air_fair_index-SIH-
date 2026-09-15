import React from 'react';
import { Plane, ShieldCheck, ExternalLink, ArrowUpRight, Github, Twitter, Linkedin } from 'lucide-react';

export default function Footer({ onOpenWhitepaper }) {
  return (
    <footer className="bg-slate-950 border-t border-slate-800/80 text-slate-400 text-xs pt-16 pb-12">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 space-y-12">
        
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
          
          {/* Col 1: Brand Info */}
          <div className="space-y-4 md:col-span-1">
            <div className="flex items-center space-x-2">
              <div className="w-8 h-8 rounded-lg bg-sky-500 flex items-center justify-center text-white font-bold">
                <Plane className="w-4 h-4" />
              </div>
              <span className="text-lg font-extrabold text-white tracking-tight font-sans">APEX-IND</span>
            </div>
            <p className="text-slate-400 text-xs leading-relaxed">
              India’s premier real-time airfare price index benchmark, powered by Multilateral GEKS-Jevons
              aggregation and route-weighted by real DGCA passenger traffic share.
            </p>
            <div className="flex items-center space-x-3 text-slate-500 pt-1">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span className="text-[11px]">DGCA & MoSPI Methodology Compliant</span>
            </div>
          </div>

          {/* Col 2: Navigation */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase text-white tracking-wider">Methodology</h4>
            <ul className="space-y-2">
              <li><a href="#pipeline" className="hover:text-sky-400 transition-colors">4.2M Ingestion Pipeline</a></li>
              <li><a href="#deduplication" className="hover:text-sky-400 transition-colors">Ancillary Noise Filter</a></li>
              <li><a href="#booking-windows" className="hover:text-sky-400 transition-colors">T-0 to T-45 Lead Windows</a></li>
              <li><a href="#geks-methodology" className="hover:text-sky-400 transition-colors">Multilateral GEKS Math</a></li>
              <li><a href="#mospi-calibration" className="hover:text-sky-400 transition-colors">MoSPI CPI Transport Alignment</a></li>
            </ul>
          </div>

          {/* Col 3: Data & API */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase text-white tracking-wider">Data Services</h4>
            <ul className="space-y-2">
              <li><a href="#dashboard" className="hover:text-sky-400 transition-colors flex items-center gap-1">Live Airfare Dashboard <ArrowUpRight className="w-3 h-3" /></a></li>
              <li><button onClick={onOpenWhitepaper} className="hover:text-sky-400 transition-colors text-left">Technical Whitepaper PDF</button></li>
              <li><a href="#dashboard" className="hover:text-sky-400 transition-colors">Historical CSV Export</a></li>
              <li><a href="#dashboard" className="hover:text-sky-400 transition-colors">Corridor Inflation Heatmaps</a></li>
            </ul>
          </div>

          {/* Col 4: Standard Compliance */}
          <div className="space-y-3">
            <h4 className="text-xs font-bold uppercase text-white tracking-wider">Index Standards</h4>
            <div className="p-3.5 rounded-2xl bg-slate-900 border border-slate-800 space-y-2">
              <span className="text-[11px] font-mono text-sky-400 block font-bold">GEKS Rolling 13M</span>
              <p className="text-[11px] text-slate-400">
                Eliminates non-transitivity and upward chain drift in dynamic airline yield management systems.
              </p>
            </div>
          </div>

        </div>

        {/* Bottom Strip */}
        <div className="pt-8 border-t border-slate-900 flex flex-col sm:flex-row items-center justify-between gap-4 text-[11px] text-slate-500">
          <p>© 2026 APEX-IND Airfare Intelligence Platform. Built for India Macro & Aviation Analytics.</p>
          <div className="flex items-center space-x-6">
            <a href="#" className="hover:text-slate-300">Privacy Policy</a>
            <a href="#" className="hover:text-slate-300">API Terms</a>
            <a href="#" className="hover:text-slate-300">MoSPI Compliance Documentation</a>
          </div>
        </div>

      </div>
    </footer>
  );
}
