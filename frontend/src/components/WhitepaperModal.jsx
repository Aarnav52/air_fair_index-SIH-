import React from 'react';
import { X, FileText, Download, ShieldCheck, Calculator, Database, Layers } from 'lucide-react';

export default function WhitepaperModal({ isOpen, onClose }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/80 backdrop-blur-md overflow-y-auto">
      
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-3xl shadow-2xl overflow-hidden text-slate-200 my-8">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <FileText className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-lg font-extrabold text-white">APEX-IND Technical Methodology Paper</h3>
              <p className="text-xs text-slate-400">Elementary Jevons — live • MoSPI Calibration & GEKS Transitivity — roadmap</p>
            </div>
          </div>

          <button 
            onClick={onClose}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Paper Content Body */}
        <div className="p-6 sm:p-8 space-y-8 max-h-[75vh] overflow-y-auto text-sm leading-relaxed">
          
          {/* Abstract */}
          <div className="p-5 rounded-2xl bg-sky-950/40 border border-sky-500/30 space-y-2">
            <h4 className="text-xs font-bold text-sky-400 uppercase tracking-wider">Abstract & Scope</h4>
            <p className="text-xs text-slate-300">
              APEX-IND targets the persistent issue of chain drift in high-frequency airfare indexing
              across Indian domestic aviation routes. The elementary layer — Jevons price relatives,
              geometric-mean aggregated — is built and running on real, live-scraped data today.
              Multilateral GEKS-Jevons aggregation (Gini-Eltetö-Köves-Szulc) across a rolling window,
              and route-weighting by real DGCA passenger traffic share, are the next implementation
              phase, described below as the target methodology.
            </p>
          </div>

          {/* Section 1: Ingestion & Deduplication */}
          <div className="space-y-3">
            <h4 className="text-base font-bold text-white flex items-center gap-2">
              <Database className="w-4 h-4 text-sky-400" />
              1. Ingestion Pipeline & Ancillary Noise Filtering
            </h4>
            <p className="text-slate-300">
              Airfare pricing engines generate significant pricing noise due to unbundled ancillaries
              (seat assignment, meals, priority check-in) and convenience fee surges. APEX-IND deploys
              automated, compliance-gated scrapers (SerpApi plus direct Akasa Air and SpiceJet collection,
              every 6 hours for T+1 fares and daily for T+30) across 7 domestic routes today, with 2,500+
              real fare points collected so far — the remaining T+7/T+15/T+45 booking windows and
              additional routes are next on the roadmap.
            </p>
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs font-mono text-slate-300 space-y-1">
              <p className="text-sky-400">// Noise Filtering Rule</p>
              <p>BaseFare = ScrapedFare - (BaggageAddon + SeatFee + PaymentSurcharge)</p>
              <p>If (GhostInventoryFlag == True) -&gt; Discard Observation</p>
            </div>
          </div>

          {/* Section 2: Multilateral GEKS Formulation */}
          <div className="space-y-3">
            <h4 className="text-base font-bold text-white flex items-center gap-2">
              <Calculator className="w-4 h-4 text-sky-400" />
              2. Multilateral GEKS Index Formulation — target methodology, next build phase
            </h4>
            <p className="text-slate-300">
              Chained bilateral indices suffer from non-transitivity ($P_{a,b} \times P_{b,c} \neq P_{a,c}$)
              when fares bounce back after promotional periods. The Multilateral GEKS index resolves
              this by calculating the geometric mean of all bilateral Jevons links. The elementary Jevons
              layer below it is already implemented and verified against real data; this multilateral
              rollup is the designed target, not yet computed on the live index:
            </p>

            <div className="p-4 rounded-xl bg-slate-950 border border-sky-500/30 text-center font-mono text-sky-300 text-sm">
              GEKS<sub>j,k</sub> = &prod;<sub>l=1</sub><sup>M</sup> ( P<sub>j,l</sub><sup>Jevons</sup> &bull; P<sub>l,k</sub><sup>Jevons</sup> ) <sup>1/M</sup>
            </div>
          </div>

          {/* Section 3: MoSPI Passenger Volume Calibration */}
          <div className="space-y-3">
            <h4 className="text-base font-bold text-white flex items-center gap-2">
              <Layers className="w-4 h-4 text-sky-400" />
              3. DGCA Passenger Traffic-Share Weighting — data collected, weighting not yet applied
            </h4>
            <p className="text-slate-300">
              Real DGCA (Directorate General of Civil Aviation) monthly passenger traffic volume is
              already collected for 6 of today's 7 active routes (e.g. 291,500/month for Delhi-Mumbai
              down to 88,500/month for Bengaluru-Hyderabad). Route weights are designed to be calibrated
              from this data — so high-traffic corridors carry proportionally accurate importance in the
              composite index, deliberately without relying on expenditure-weight data, since scraped
              price quotes carry none — but this weighting is not yet wired into the live index
              computation; every route currently counts equally.
            </p>
          </div>

        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-slate-950/60">
          <span className="text-xs text-slate-400">© 2026 APEX-IND Intelligence Project</span>
          <button
            onClick={onClose}
            className="px-5 py-2 text-xs font-bold rounded-xl text-white bg-sky-600 hover:bg-sky-500 transition-colors"
          >
            Close Document
          </button>
        </div>

      </div>
    </div>
  );
}
