import React from 'react';
import {
  Calendar,
  UploadCloud,
  FileText,
  Clock,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  Users,
  Building
} from 'lucide-react';
import { DashboardSummary } from '../types';
import { DashboardCards } from '../components/DashboardCards';
import { TrendChart } from '../components/TrendChart';
import { formatNYDateTime } from '../utils/dateUtils';

interface DashboardPageProps {
  summary: DashboardSummary;
  onNavigate: (tab: string) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ summary, onNavigate }) => {
  return (
    <div className="space-y-6">
      {/* Missing Dates Banner (if any) */}
      {summary.missing_reporting_dates_count > 0 && (
        <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3 text-amber-200">
          <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
          <div className="text-sm">
            <span className="font-bold text-amber-300">Reporting Date Gap Detected:</span> The active rolling window
            contains {summary.missing_reporting_dates_count} missing calendar date(s):{' '}
            <strong className="text-white font-mono">{summary.missing_dates.join(', ')}</strong>. Upload reports for
            these missing dates to maintain unbroken coverage.
          </div>
        </div>
      )}

      {/* KPI Cards */}
      <DashboardCards summary={summary} onNavigate={onNavigate} />

      {/* Main Grid: Trends & Latest Import */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Guest Appearance Trend Chart (2 cols) */}
        <div className="lg:col-span-2 rounded-xl bg-slate-900 border border-slate-800 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
                <Users className="w-4 h-4 text-amber-400" /> Daily Departure Trends
              </h2>
              <p className="text-xs text-slate-400">Total departed guest records per reporting date</p>
            </div>
            <button
              onClick={() => onNavigate('records')}
              className="text-xs text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-1 transition-colors"
            >
              <span>View All Records</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <TrendChart data={summary.appearance_trends} />
        </div>

        {/* Latest Import Info & Quick Action (1 col) */}
        <div className="rounded-xl bg-slate-900 border border-slate-800 p-5 flex flex-col justify-between space-y-4">
          <div>
            <h2 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
              <Clock className="w-4 h-4 text-amber-400" /> Latest Successful Import
            </h2>
            <p className="text-xs text-slate-400">Most recent report committed to database</p>

            {summary.latest_import ? (
              <div className="mt-4 p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    Active & Processed
                  </span>
                  <span className="text-[11px] text-slate-400 font-mono" title="Processed in America/New_York time">
                    {formatNYDateTime(summary.latest_import.imported_at)}
                  </span>
                </div>

                <div className="text-sm font-bold text-white truncate" title={summary.latest_import.filename}>
                  {summary.latest_import.filename}
                </div>

                <div className="text-xs text-slate-300 space-y-1 pt-1 border-t border-slate-700/40">
                  <div className="flex justify-between">
                    <span className="text-slate-400">Reporting Date:</span>
                    <strong className="text-amber-300 font-mono">{summary.latest_import.report_date}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-400">Records Extracted:</span>
                    <strong className="text-white font-mono">{summary.latest_import.records_count}</strong>
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-4 p-6 rounded-xl bg-slate-800/30 border border-dashed border-slate-700 text-center text-xs text-slate-400">
                No reports imported yet.
              </div>
            )}
          </div>

          {/* Quick CTA */}
          <div className="pt-2">
            <button
              onClick={() => onNavigate('upload')}
              className="w-full py-2.5 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-bold text-sm shadow-md shadow-amber-500/20 flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
            >
              <UploadCloud className="w-4 h-4" />
              <span>Upload Daily PDF Report</span>
            </button>
          </div>
        </div>
      </div>

      {/* Recent Upload History Table */}
      <div className="rounded-xl bg-slate-900 border border-slate-800 p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-white tracking-tight flex items-center gap-2">
              <FileText className="w-4 h-4 text-amber-400" /> Recent Upload Activity
            </h2>
            <p className="text-xs text-slate-400">Chronological history of daily departure files</p>
          </div>
          <button
            onClick={() => onNavigate('history')}
            className="text-xs text-amber-400 hover:text-amber-300 font-semibold flex items-center gap-1 transition-colors"
          >
            <span>View All History</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="border border-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-950/80 text-slate-400 text-xs font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Filename</th>
                <th className="py-3 px-4">Reporting Date</th>
                <th className="py-3 px-4">Records</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Imported At (NY Time)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-300">
              {summary.recent_reports.length > 0 ? (
                summary.recent_reports.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-4 font-mono text-xs text-white font-semibold">{r.filename}</td>
                    <td className="py-3 px-4 font-mono text-xs text-amber-300">{r.report_date}</td>
                    <td className="py-3 px-4 font-mono text-xs">{r.rows}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {r.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-xs font-mono text-slate-400">
                      {formatNYDateTime(r.created_at)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500 text-xs">
                    No upload activity recorded yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
