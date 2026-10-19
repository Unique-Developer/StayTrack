import React, { useState, useEffect } from 'react';
import {
  Users,
  Flame,
  CalendarCheck,
  Search,
  Filter,
  Download,
  FileText,
  ChevronRight,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Sparkles
} from 'lucide-react';
import { api } from '../services/api';
import { GuestAssessmentItem, GuestMonitoringResponse } from '../types';
import { GuestDetailModal } from '../components/GuestDetailModal';

export const GuestMonitoringPage: React.FC = () => {
  const [activeMode, setActiveMode] = useState<'continuous_stay' | 'repeated_appearance'>('continuous_stay');
  const [data, setData] = useState<GuestMonitoringResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [verificationFilter, setVerificationFilter] = useState('');
  const [roomFilter, setRoomFilter] = useState('');
  const [selectedGuestId, setSelectedGuestId] = useState<number | null>(null);

  const loadData = () => {
    setLoading(true);
    api.getGuestMonitoring({
      mode: activeMode,
      search: search || undefined,
      verification_status: verificationFilter || undefined,
      room: roomFilter || undefined,
      page: 1,
      page_size: 100,
    })
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, [activeMode, verificationFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    loadData();
  };

  const handleResetFilters = () => {
    setSearch('');
    setVerificationFilter('');
    setRoomFilter('');
    setTimeout(loadData, 0);
  };

  const handleExportCsv = () => {
    const url = api.getGuestExportUrl({
      mode: activeMode,
      verification_status: verificationFilter || undefined,
      search: search || undefined,
    });
    window.open(url, '_blank');
  };

  const handleExportPdf = () => {
    const url = api.getGuestExportPdfUrl({
      search: search || undefined,
    });
    window.open(url, '_blank');
  };

  return (
    <div className="space-y-6">
      {/* Page Title & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <Users className="w-6 h-6 text-amber-400" /> Guest Monitoring
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Continuous occupancy and repeated pattern analysis across the rolling 30-day reporting window.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleExportCsv}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-all shadow-sm"
          >
            <Download className="w-4 h-4 text-amber-400" />
            <span>Export CSV</span>
          </button>

          <button
            onClick={handleExportPdf}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-all shadow-sm hover:border-rose-500/40"
            title="Export Long-Stay PDF Report"
          >
            <FileText className="w-4 h-4 text-rose-400" />
            <span>Export PDF</span>
          </button>
        </div>
      </div>

      {/* Mode Tabs (Mode A vs Mode B) */}
      <div className="flex flex-col sm:flex-row p-1.5 rounded-xl bg-slate-900 border border-slate-800 gap-2">
        <button
          onClick={() => setActiveMode('continuous_stay')}
          className={`flex-1 flex items-center justify-center gap-2.5 py-3 px-4 rounded-lg text-xs font-bold transition-all ${
            activeMode === 'continuous_stay'
              ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 font-black'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          }`}
        >
          <Flame className={`w-4 h-4 ${activeMode === 'continuous_stay' ? 'text-slate-950' : 'text-amber-400'}`} />
          <span>Mode A: Continuous Stay Detection</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono ${
              activeMode === 'continuous_stay' ? 'bg-slate-950 text-amber-400' : 'bg-slate-800 text-slate-400'
            }`}
          >
            &gt;= 30 Days
          </span>
        </button>

        <button
          onClick={() => setActiveMode('repeated_appearance')}
          className={`flex-1 flex items-center justify-center gap-2.5 py-3 px-4 rounded-lg text-xs font-bold transition-all ${
            activeMode === 'repeated_appearance'
              ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 font-black'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          }`}
        >
          <CalendarCheck
            className={`w-4 h-4 ${activeMode === 'repeated_appearance' ? 'text-slate-950' : 'text-amber-400'}`}
          />
          <span>Mode B: Repeated Daily Appearance Detection</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono ${
              activeMode === 'repeated_appearance' ? 'bg-slate-950 text-amber-400' : 'bg-slate-800 text-slate-400'
            }`}
          >
            &gt;= 3 Reports
          </span>
        </button>
      </div>

      {/* Mode Description Info Box */}
      <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300">
        {activeMode === 'continuous_stay' ? (
          <div>
            <strong className="text-amber-400">Mode A Rules:</strong> Evaluates uninterrupted occupancy evidence
            (check-in date to departure date and continuous reservation chains). Guests meeting or exceeding 30
            consecutive days are flagged for continuous residency / long-stay tax tracking.
          </div>
        ) : (
          <div>
            <strong className="text-amber-400">Mode B Rules:</strong> Counts distinct daily departure reports in which a
            matching guest identity appeared. Guests appearing repeatedly (default &gt;= 3 distinct reports) are flagged
            for frequent/extended guest review regardless of reservation breaks.
          </div>
        )}
      </div>

      {/* Filter Bar */}
      <form onSubmit={handleSearchSubmit} className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search guest name, room, or confirmation #..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-800 focus:border-amber-400 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none"
          />
        </div>

        <select
          value={verificationFilter}
          onChange={(e) => setVerificationFilter(e.target.value)}
          className="bg-slate-900 border border-slate-800 focus:border-amber-400 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none"
        >
          <option value="">All Verification Statuses</option>
          <option value="Verified">Verified Only</option>
          <option value="Needs Verification">Needs Verification Only</option>
        </select>

        <button
          type="submit"
          className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-lg text-xs transition-colors"
        >
          Filter
        </button>

        {(search || verificationFilter || roomFilter) && (
          <button
            type="button"
            onClick={handleResetFilters}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
            title="Reset Filters"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        )}
      </form>

      {/* Data Table */}
      <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Guest Name</th>
                <th className="py-3 px-4">Room History</th>
                {activeMode === 'continuous_stay' ? (
                  <>
                    <th className="py-3 px-4">Check-In Date</th>
                    <th className="py-3 px-4">Calculated Departure</th>
                    <th className="py-3 px-4">Stay Duration</th>
                  </>
                ) : (
                  <>
                    <th className="py-3 px-4">Report Dates Count</th>
                    <th className="py-3 px-4">First Appearance</th>
                    <th className="py-3 px-4">Last Appearance</th>
                  </>
                )}
                <th className="py-3 px-4">Verification</th>
                <th className="py-3 px-4">Evidence & Notes</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={7} className="py-10 text-center text-slate-500 animate-pulse">
                    Loading guest monitoring records...
                  </td>
                </tr>
              ) : data?.items && data.items.length > 0 ? (
                data.items.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => setSelectedGuestId(item.guest_identity_id)}
                    className="hover:bg-slate-800/40 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4">
                      <div className="font-bold text-white group-hover:text-amber-400 transition-colors">
                        {item.guest_name}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                        Conf: {item.confirmation_numbers.join(', ') || 'N/A'}
                      </div>
                    </td>

                    <td className="py-3 px-4 font-mono">
                      <div className="flex flex-wrap gap-1">
                        {item.rooms.map((rm, rIdx) => (
                          <span
                            key={rIdx}
                            className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200 border border-slate-700 font-bold text-[10px]"
                          >
                            Rm {rm}
                          </span>
                        ))}
                      </div>
                    </td>

                    {activeMode === 'continuous_stay' ? (
                      <>
                        <td className="py-3 px-4 font-mono text-slate-300">{item.first_date || 'N/A'}</td>
                        <td className="py-3 px-4 font-mono text-slate-300">{item.last_date || 'N/A'}</td>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded-full font-mono font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs">
                            {item.stay_duration_days} Days
                          </span>
                        </td>
                      </>
                    ) : (
                      <>
                        <td className="py-3 px-4">
                          <span className="px-2 py-0.5 rounded-full font-mono font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30 text-xs">
                            {item.reporting_dates_count} Dates
                          </span>
                        </td>
                        <td className="py-3 px-4 font-mono text-slate-300">{item.first_date || 'N/A'}</td>
                        <td className="py-3 px-4 font-mono text-slate-300">{item.last_date || 'N/A'}</td>
                      </>
                    )}

                    <td className="py-3 px-4">
                      {item.verification_status === 'Verified' ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="w-3 h-3" /> Verified
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                          <AlertTriangle className="w-3 h-3" /> Needs Review
                        </span>
                      )}
                    </td>

                    <td className="py-3 px-4 max-w-xs truncate text-[11px] text-slate-400">
                      {item.evidence_source || item.notes}
                    </td>

                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedGuestId(item.guest_identity_id);
                        }}
                        className="p-1 rounded-lg hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500 text-xs">
                    No guests currently meet the {activeMode === 'continuous_stay' ? '30-day continuous stay' : '3+ repeated appearance'} criteria in the active window.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Guest Detail Slide-Over Modal */}
      <GuestDetailModal identityId={selectedGuestId} onClose={() => setSelectedGuestId(null)} />
    </div>
  );
};
