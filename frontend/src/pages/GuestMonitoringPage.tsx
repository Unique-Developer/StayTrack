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
  Sparkles,
  GitMerge,
  Building2,
  Award,
  ShieldCheck,
  X
} from 'lucide-react';
import { api } from '../services/api';
import { GuestAssessmentItem, GuestMonitoringResponse, Property } from '../types';
import { GuestDetailModal } from '../components/GuestDetailModal';
import { useProperty } from '../context/PropertyContext';
import { MotelSwitcher } from '../components/MotelSwitcher';

export const GuestMonitoringPage: React.FC = () => {
  const { currentPropertyId, currentProperty } = useProperty();
  const [activeMode, setActiveMode] = useState<'continuous_stay_90' | 'continuous_stay' | 'repeated_appearance'>('continuous_stay_90');
  const [data, setData] = useState<GuestMonitoringResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [verificationFilter, setVerificationFilter] = useState('');
  const [roomFilter, setRoomFilter] = useState('');
  const [selectedGuestId, setSelectedGuestId] = useState<number | null>(null);

  // Multi-selection for customer merge
  const [selectedIdentityIds, setSelectedIdentityIds] = useState<Set<number>>(new Set());
  const [mergeModalOpen, setMergeModalOpen] = useState(false);
  const [primaryMergeId, setPrimaryMergeId] = useState<number | null>(null);
  const [mergeProcessing, setMergeProcessing] = useState(false);
  const [banner, setBanner] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const toggleSelectIdentity = (id: number) => {
    setSelectedIdentityIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleToggleSelectAll = () => {
    if (!data?.items) return;
    const currentItemIds = data.items.map((i) => i.guest_identity_id);
    const allSelected = currentItemIds.every((id) => selectedIdentityIds.has(id));
    if (allSelected) {
      setSelectedIdentityIds(new Set());
    } else {
      setSelectedIdentityIds(new Set(currentItemIds));
    }
  };

  const openMergeDialog = () => {
    if (selectedIdentityIds.size < 2) return;
    const firstId = Array.from(selectedIdentityIds)[0];
    setPrimaryMergeId(firstId);
    setMergeModalOpen(true);
  };

  const handleConfirmCustomerMerge = async () => {
    if (!primaryMergeId || selectedIdentityIds.size < 2) return;
    setMergeProcessing(true);
    try {
      const secondaryIds = Array.from(selectedIdentityIds).filter((id) => id !== primaryMergeId);
      const res = await api.mergeGuests({
        primary_identity_id: primaryMergeId,
        secondary_identity_ids: secondaryIds,
      });
      setBanner({
        type: 'success',
        message: res.message || 'Customers merged successfully.',
      });
      setSelectedIdentityIds(new Set());
      setMergeModalOpen(false);
      loadData();
    } catch (err: any) {
      setBanner({
        type: 'error',
        message: err.message || 'Failed to merge selected customers.',
      });
    } finally {
      setMergeProcessing(false);
    }
  };

  const loadData = () => {
    setLoading(true);
    api.getGuestMonitoring({
      mode: activeMode,
      property_id: currentPropertyId,
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
  }, [activeMode, verificationFilter, currentPropertyId]);

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
      property_id: currentPropertyId,
      verification_status: verificationFilter || undefined,
      search: search || undefined,
    });
    window.open(url, '_blank');
  };

  const handleExportPdf = () => {
    const minNights = activeMode === 'continuous_stay_90' ? 90 : (activeMode === 'continuous_stay' ? 30 : 1);
    const url = api.getGuestExportPdfUrl({
      search: search || undefined,
      property_id: currentPropertyId,
      min_nights: minNights,
    });
    window.open(url, '_blank');
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Banner */}
      {banner && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between gap-3 text-xs font-semibold ${
            banner.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/10 border-rose-500/30 text-rose-300'
          }`}
        >
          <div className="flex items-center gap-2">
            {banner.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span>{banner.message}</span>
          </div>
          <button
            onClick={() => setBanner(null)}
            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Page Title & Actions */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <Users className="w-6 h-6 text-amber-400" /> Guest Monitoring & Tax Exemption
          </h1>
          <p className="text-xs text-slate-400 mt-1 flex items-center gap-2">
            <span>Occupancy tracking & tax exemption milestones for</span>
            <span className="font-bold text-amber-400">{currentProperty?.name || 'Selected Motel'}</span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Motel Switcher */}
          <MotelSwitcher variant="header" />

          {selectedIdentityIds.size >= 2 && (
            <button
              onClick={openMergeDialog}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black transition-all shadow-md shadow-amber-500/20"
            >
              <GitMerge className="w-4 h-4" />
              <span>Merge Selected Guests ({selectedIdentityIds.size})</span>
            </button>
          )}

          <button
            onClick={handleExportCsv}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-all shadow-sm"
          >
            <Download className="w-4 h-4 text-amber-400" />
            <span>{activeMode === 'continuous_stay_90' ? 'Export 90+ CSV' : 'Export CSV'}</span>
          </button>

          <button
            onClick={handleExportPdf}
            className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-all shadow-sm hover:border-rose-500/40"
            title="Export Long-Stay PDF Report"
          >
            <FileText className="w-4 h-4 text-rose-400" />
            <span>{activeMode === 'continuous_stay_90' ? 'Export 90+ PDF' : 'Export PDF'}</span>
          </button>
        </div>
      </div>

      {/* Mode Tabs: 3 Tabs (90+ Days, 30+ Days, Mode B) */}
      <div className="flex flex-col sm:flex-row p-1.5 rounded-xl bg-slate-900 border border-slate-800 gap-2">
        {/* Tab 1: 90+ Days Guest List */}
        <button
          onClick={() => setActiveMode('continuous_stay_90')}
          className={`flex-1 flex items-center justify-center gap-2.5 py-3 px-4 rounded-lg text-xs font-bold transition-all cursor-pointer ${
            activeMode === 'continuous_stay_90'
              ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 shadow-md shadow-emerald-500/25 font-black scale-[1.01]'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          }`}
        >
          <Award className={`w-4 h-4 ${activeMode === 'continuous_stay_90' ? 'text-slate-950' : 'text-emerald-400'}`} />
          <span>90+ Days Guest List</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold ${
              activeMode === 'continuous_stay_90' ? 'bg-slate-950 text-emerald-300' : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
            }`}
          >
            State & County Exempt (&gt;= 90d)
          </span>
        </button>

        {/* Tab 2: 30+ Days Continuous Stay */}
        <button
          onClick={() => setActiveMode('continuous_stay')}
          className={`flex-1 flex items-center justify-center gap-2.5 py-3 px-4 rounded-lg text-xs font-bold transition-all cursor-pointer ${
            activeMode === 'continuous_stay'
              ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 shadow-md shadow-amber-500/20 font-black scale-[1.01]'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          }`}
        >
          <Flame className={`w-4 h-4 ${activeMode === 'continuous_stay' ? 'text-slate-950' : 'text-amber-400'}`} />
          <span>30+ Days Continuous Stay</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold ${
              activeMode === 'continuous_stay' ? 'bg-slate-950 text-amber-400' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
            }`}
          >
            County Exempt Only (&gt;= 30d)
          </span>
        </button>

        {/* Tab 3: Mode B: Repeated Appearance Detection */}
        <button
          onClick={() => setActiveMode('repeated_appearance')}
          className={`flex-1 flex items-center justify-center gap-2.5 py-3 px-4 rounded-lg text-xs font-bold transition-all cursor-pointer ${
            activeMode === 'repeated_appearance'
              ? 'bg-gradient-to-r from-sky-500 to-sky-600 text-slate-950 shadow-md shadow-sky-500/20 font-black scale-[1.01]'
              : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
          }`}
        >
          <CalendarCheck
            className={`w-4 h-4 ${activeMode === 'repeated_appearance' ? 'text-slate-950' : 'text-sky-400'}`}
          />
          <span>Repeated Appearances (Mode B)</span>
          <span
            className={`px-2 py-0.5 rounded-full text-[10px] font-mono font-bold ${
              activeMode === 'repeated_appearance' ? 'bg-slate-950 text-sky-300' : 'bg-sky-500/10 text-sky-400 border border-sky-500/20'
            }`}
          >
            &gt;= 3 Reports
          </span>
        </button>
      </div>

      {/* Mode Description Info Box */}
      <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 text-xs text-slate-300">
        {activeMode === 'continuous_stay_90' ? (
          <div>
            <strong className="text-emerald-400">90+ Days State & County Tax Exemption Rules:</strong> Evaluates uninterrupted occupancy of 90 or more consecutive nights. Guests in this tier are fully exempt from both Virginia State Sales Tax and Local/County Occupancy Tax. Displays exact County Exempt Date (Day 31), State Exempt Date (Day 91), and negotiated fixed rates.
          </div>
        ) : activeMode === 'continuous_stay' ? (
          <div>
            <strong className="text-amber-400">30+ Days Continuous Stay Rules:</strong> Evaluates uninterrupted occupancy of 30 or more consecutive days (check-in date to departure date across continuous reservation chains). Guests meeting or exceeding 30 consecutive days qualify for County / Local Occupancy Tax Exemption.
          </div>
        ) : (
          <div>
            <strong className="text-sky-400">Mode B Rules:</strong> Counts distinct daily departure reports in which a
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
                <th className="py-3 px-3 w-10 text-center">
                  <input
                    type="checkbox"
                    checked={
                      (data?.items?.length || 0) > 0 &&
                      data?.items?.every((i) => selectedIdentityIds.has(i.guest_identity_id))
                    }
                    onChange={handleToggleSelectAll}
                    className="w-4 h-4 rounded text-amber-500 bg-slate-900 border-slate-700 focus:ring-amber-400 cursor-pointer accent-amber-500"
                    title="Select all on this page"
                  />
                </th>
                <th className="py-3 px-4">Guest Name</th>
                <th className="py-3 px-4">Room#</th>
                {activeMode !== 'repeated_appearance' ? (
                  <>
                    <th className="py-3 px-4">Check-In Date</th>
                    <th className="py-3 px-4">Calculated Departure</th>
                    <th className="py-3 px-4">Duration & Tier</th>
                    <th className="py-3 px-4">County Exempt (30+)</th>
                    <th className="py-3 px-4">State Exempt (90+)</th>
                    <th className="py-3 px-4">Tax Status</th>
                    <th className="py-3 px-4">Fixed Rate</th>
                  </>
                ) : (
                  <>
                    <th className="py-3 px-4">Report Dates Count</th>
                    <th className="py-3 px-4">First Appearance</th>
                    <th className="py-3 px-4">Last Appearance</th>
                    <th className="py-3 px-4">Verification</th>
                    <th className="py-3 px-4">Evidence & Notes</th>
                  </>
                )}
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={10} className="py-10 text-center text-slate-500 animate-pulse">
                    Loading guest monitoring records...
                  </td>
                </tr>
              ) : data?.items && data.items.length > 0 ? (
                data.items.map((item) => {
                  const isSelected = selectedIdentityIds.has(item.guest_identity_id);
                  return (
                    <tr
                      key={item.id}
                      onClick={() => setSelectedGuestId(item.guest_identity_id)}
                      className={`hover:bg-slate-800/40 transition-colors cursor-pointer group ${
                        isSelected ? 'bg-amber-500/5' : ''
                      }`}
                    >
                      <td
                        className="py-3 px-3 text-center"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSelectIdentity(item.guest_identity_id);
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => {}}
                          className="w-4 h-4 rounded text-amber-500 bg-slate-900 border-slate-700 focus:ring-amber-400 cursor-pointer accent-amber-500"
                        />
                      </td>

                      <td className="py-3 px-4">
                        <div className="font-bold text-white group-hover:text-amber-400 transition-colors">
                          {item.guest_name}
                        </div>
                        <div className="text-[10px] text-slate-500 font-mono mt-0.5">
                          ID: #{item.guest_identity_id} • Conf: {item.confirmation_numbers.join(', ') || 'N/A'}
                        </div>
                      </td>

                      <td className="py-3 px-4 font-mono">
                        <div className="flex flex-wrap gap-1">
                          {item.rooms.length > 0 ? (
                            item.rooms.map((rm, rIdx) => (
                              <span
                                key={rIdx}
                                className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-200 border border-slate-700 font-bold text-[10px]"
                              >
                                Rm {rm}
                              </span>
                            ))
                          ) : (
                            <span className="text-slate-500 text-[10px]">—</span>
                          )}
                        </div>
                      </td>

                      {activeMode !== 'repeated_appearance' ? (
                        <>
                          <td className="py-3 px-4 font-mono font-bold text-slate-200">{item.first_date || 'N/A'}</td>
                          <td className="py-3 px-4 font-mono text-slate-300">{item.last_date || 'N/A'}</td>
                          <td className="py-3 px-4">
                            <div className="space-y-1">
                              <span className="px-2 py-0.5 rounded-full font-mono font-bold bg-amber-500/20 text-amber-400 border border-amber-500/30 text-xs">
                                {item.stay_duration_days} Days
                              </span>
                              <div>
                                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                                  item.stay_duration_days >= 90
                                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                                    : item.stay_duration_days >= 30
                                    ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                                    : item.stay_duration_days >= 21
                                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                                    : 'bg-sky-500/20 text-sky-400 border border-sky-500/30'
                                }`}>
                                  {item.tier_category || (item.stay_duration_days >= 90 ? '90+ Nights' : item.stay_duration_days >= 30 ? '30–89 Nights' : item.stay_duration_days >= 21 ? '21–29 Nights' : '7–20 Nights')}
                                </span>
                              </div>
                            </div>
                          </td>
                          <td className="py-3 px-4 font-mono text-amber-300 font-semibold">{item.county_exempt_date || 'N/A'}</td>
                          <td className="py-3 px-4 font-mono text-emerald-400 font-semibold">{item.state_exempt_date || 'N/A'}</td>
                          <td className="py-3 px-4">
                            <span className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full ${
                              item.stay_duration_days >= 90
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                : item.stay_duration_days >= 30
                                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                                : item.stay_duration_days >= 21
                                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/30'
                                : 'bg-slate-800 text-slate-400 border border-slate-700'
                            }`}>
                              {item.tax_exempt_status || (item.stay_duration_days >= 90 ? 'State & County Exempt' : item.stay_duration_days >= 30 ? 'County Exempt Only' : 'Taxable')}
                            </span>
                          </td>
                          <td className="py-3 px-4 font-mono font-bold text-emerald-400">
                            {item.fixed_rate !== undefined && item.fixed_rate !== null ? `$${item.fixed_rate.toFixed(2)}` : <span className="text-slate-500 font-normal">—</span>}
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
                        </>
                      )}

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
                  );
                })
              ) : (
                <tr>
                  <td colSpan={8} className="py-12 text-center text-slate-500 text-xs">
                    No guests currently meet the {activeMode === 'continuous_stay' ? '30-day continuous stay' : '3+ repeated appearance'} criteria in the active window.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Floating Action Dock for Multi-Selection Merge */}
      {selectedIdentityIds.size >= 2 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-slate-900/95 backdrop-blur-md border border-amber-500/40 shadow-2xl rounded-2xl px-5 py-3 flex items-center gap-4 text-xs animate-in slide-in-from-bottom-5 duration-200">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
            <span className="font-bold text-white">
              <strong className="text-amber-400 font-mono text-sm">{selectedIdentityIds.size}</strong> guests selected
            </span>
          </div>

          <div className="h-4 w-px bg-slate-700" />

          <button
            onClick={() => setSelectedIdentityIds(new Set())}
            className="text-slate-400 hover:text-white transition-colors"
          >
            Clear Selection
          </button>

          <button
            onClick={openMergeDialog}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold transition-all shadow-md shadow-amber-500/20"
          >
            <GitMerge className="w-4 h-4" />
            <span>Merge Selected Customers ({selectedIdentityIds.size})</span>
          </button>
        </div>
      )}

      {/* Customer Profile Merge Modal */}
      {mergeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-700 w-full max-w-lg rounded-2xl shadow-2xl p-6 space-y-5 animate-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between gap-4 border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center">
                  <GitMerge className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">
                    Merge {selectedIdentityIds.size} Customer Profiles
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Choose the primary profile to retain. All history and rooms will merge into it.
                  </p>
                </div>
              </div>

              {!mergeProcessing && (
                <button
                  onClick={() => setMergeModalOpen(false)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>

            <div className="space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Select Primary Customer Profile:
              </div>
              <div className="max-h-60 overflow-y-auto space-y-2">
                {data?.items
                  ?.filter((i) => selectedIdentityIds.has(i.guest_identity_id))
                  .map((item) => (
                    <label
                      key={item.guest_identity_id}
                      onClick={() => setPrimaryMergeId(item.guest_identity_id)}
                      className={`p-3.5 rounded-xl border flex items-center justify-between gap-3 cursor-pointer transition-all ${
                        primaryMergeId === item.guest_identity_id
                          ? 'bg-amber-500/10 border-amber-500/60 ring-1 ring-amber-500/30'
                          : 'bg-slate-800/40 border-slate-700 hover:bg-slate-800'
                      }`}
                    >
                      <div className="space-y-1">
                        <div className="font-bold text-white text-xs flex items-center gap-2">
                          <span>{item.guest_name}</span>
                          <span className="font-mono text-[10px] text-slate-400">#{item.guest_identity_id}</span>
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          Stay: {item.stay_duration_days} Days • Rooms: {item.rooms.join(', ')}
                        </div>
                      </div>

                      <input
                        type="radio"
                        name="primaryGuest"
                        checked={primaryMergeId === item.guest_identity_id}
                        onChange={() => setPrimaryMergeId(item.guest_identity_id)}
                        className="w-4 h-4 text-amber-500 accent-amber-500 cursor-pointer"
                      />
                    </label>
                  ))}
              </div>
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setMergeModalOpen(false)}
                disabled={mergeProcessing}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={handleConfirmCustomerMerge}
                disabled={mergeProcessing || !primaryMergeId}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-all shadow-md shadow-amber-500/20 disabled:opacity-50"
              >
                {mergeProcessing ? (
                  <>
                    <RotateCcw className="w-3.5 h-3.5 animate-spin" />
                    <span>Merging Profiles...</span>
                  </>
                ) : (
                  <>
                    <GitMerge className="w-3.5 h-3.5" />
                    <span>Confirm & Merge Customers</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Guest Detail Slide-Over Modal */}
      <GuestDetailModal identityId={selectedGuestId} onClose={() => { setSelectedGuestId(null); loadData(); }} />
    </div>
  );
};
