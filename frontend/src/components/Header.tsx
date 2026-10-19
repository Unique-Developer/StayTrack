import React from 'react';
import { Calendar, UploadCloud, RefreshCw, CheckCircle2, AlertCircle } from 'lucide-react';
import { DashboardSummary } from '../types';

interface HeaderProps {
  summary?: DashboardSummary;
  onUploadClick: () => void;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Header: React.FC<HeaderProps> = ({ summary, onUploadClick, onRefresh, isRefreshing }) => {
  return (
    <header className="h-16 bg-slate-900/80 backdrop-blur-md border-b border-slate-800 px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Rolling Window Indicator */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/60 text-xs">
          <Calendar className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-slate-400 font-medium">Rolling Window:</span>
          {summary?.active_window_start && summary?.active_window_end ? (
            <span className="font-semibold text-slate-100">
              {summary.active_window_start} <span className="text-slate-500">to</span> {summary.active_window_end}
              <span className="ml-2 px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 text-[11px] font-bold">
                {summary.reporting_dates_covered} / 30 Days Active ({summary.window_coverage_pct}%)
              </span>
            </span>
          ) : (
            <span className="text-slate-400 italic">No reports imported yet</span>
          )}
        </div>

        {summary && summary.missing_reporting_dates_count > 0 && (
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-medium">
            <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
            <span>{summary.missing_reporting_dates_count} missing date(s) in span</span>
          </div>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-3">
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all border border-slate-700"
          title="Refresh Data"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-amber-400' : ''}`} />
        </button>

        <button
          onClick={onUploadClick}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-bold text-sm shadow-md shadow-amber-500/20 transition-all active:scale-[0.98]"
        >
          <UploadCloud className="w-4 h-4" />
          <span>Upload Daily Report</span>
        </button>
      </div>
    </header>
  );
};
