import React, { useEffect, useState } from 'react';
import { X, Calendar, User, Home, Hash, Clock, ShieldCheck, CheckCircle2, AlertTriangle, FileText, ArrowRight } from 'lucide-react';
import { api } from '../services/api';
import { GuestDetail } from '../types';
import { formatNYDateTime } from '../utils/dateUtils';

interface GuestDetailModalProps {
  identityId: number | null;
  onClose: () => void;
  onUpdated?: () => void;
}

export const GuestDetailModal: React.FC<GuestDetailModalProps> = ({ identityId, onClose, onUpdated }) => {
  const [detail, setDetail] = useState<GuestDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editCheckIn, setEditCheckIn] = useState('');
  const [editNotes, setEditNotes] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (!identityId) return;
    setLoading(true);
    setError(null);
    setSaveSuccess(false);
    api.getGuestDetail(identityId)
      .then(res => {
        setDetail(res);
        setEditCheckIn(res.original_check_in_date || '');
        setEditNotes(res.notes || '');
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [identityId]);

  const handleSaveTaxConfig = async () => {
    if (!detail) return;
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const res = await api.updateGuestIdentity(detail.identity_id, {
        original_check_in_date: editCheckIn.trim() || undefined,
        notes: editNotes.trim() || undefined,
      });
      setDetail(prev => prev ? {
        ...prev,
        original_check_in_date: res.original_check_in_date,
        notes: res.notes,
        county_exempt_date: res.county_exempt_date,
        state_exempt_date: res.state_exempt_date,
      } : null);
      setSaveSuccess(true);
      if (onUpdated) {
        onUpdated();
      }
      setTimeout(() => setSaveSuccess(false), 4000);
    } catch (err: any) {
      alert(err.message || 'Failed to update guest details');
    } finally {
      setIsSaving(false);
    }
  };

  if (!identityId) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="bg-slate-900 border border-slate-700 w-full max-w-4xl max-h-[90vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 border border-amber-500/30 flex items-center justify-center font-black text-lg">
              <User className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-xl font-bold text-white tracking-tight">
                  {detail?.normalized_name || 'Loading Guest Profile...'}
                </h2>
                {detail?.verification_status === 'Verified' ? (
                  <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 font-semibold">
                    <CheckCircle2 className="w-3 h-3" /> Verified
                  </span>
                ) : (
                  <span className="flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30 font-semibold">
                    <AlertTriangle className="w-3 h-3" /> Needs Verification
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Identity Profile #{identityId} • {detail?.records_count || 0} associated report record(s)
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && (
            <div className="py-20 text-center text-slate-400 animate-pulse">
              Loading full audit history and stay records...
            </div>
          )}

          {error && (
            <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-400 text-sm">
              {error}
            </div>
          )}

          {detail && (
            <>
              {/* Residency & Tax Exemption Settings Card */}
              <div className="rounded-xl bg-slate-800/50 border border-slate-700/80 p-5 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4" /> Residency & Tax Exemption Configuration
                  </h3>
                  {saveSuccess && (
                    <span className="text-xs px-2.5 py-1 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold flex items-center gap-1.5 animate-fade-in">
                      <CheckCircle2 className="w-3.5 h-3.5" /> Saved Successfully
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div>
                    <label className="block text-slate-400 font-semibold mb-1">
                      Original Check-In Date
                    </label>
                    <input
                      type="date"
                      value={editCheckIn}
                      onChange={(e) => setEditCheckIn(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white font-mono focus:border-amber-400 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-500 mt-1">Ground-truth first arrival date for continuous residency</p>
                  </div>

                  <div>
                    <label className="block text-slate-400 font-semibold mb-1">
                      Remarks / Notes
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Verified guest history, tax exempt certificate on file"
                      value={editNotes}
                      onChange={(e) => setEditNotes(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-900 border border-slate-700 text-white focus:border-amber-400 focus:outline-none"
                    />
                    <p className="text-[10px] text-slate-500 mt-1">Special agreements & audit remarks</p>
                  </div>
                </div>

                {/* Tax Milestones Calculation Summary */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-xs">
                  <div>
                    <span className="text-slate-400">County Exempt (30+ Days):</span>
                    <div className="font-bold text-amber-300 font-mono mt-0.5">
                      {detail.county_exempt_date || 'N/A (Set Check-In)'}
                    </div>
                  </div>

                  <div>
                    <span className="text-slate-400">State Exempt (90+ Days):</span>
                    <div className="font-bold text-emerald-400 font-mono mt-0.5">
                      {detail.state_exempt_date || 'N/A (Set Check-In)'}
                    </div>
                  </div>

                  <div>
                    <span className="text-slate-400">Current Tax Status:</span>
                    <div className="font-bold text-slate-200 mt-0.5">
                      {detail.tax_exempt_status || 'Standard Taxable'}
                    </div>
                  </div>
                </div>

                <div className="flex justify-end">
                  <button
                    onClick={handleSaveTaxConfig}
                    disabled={isSaving}
                    className="px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-slate-950 font-bold text-xs transition-all shadow-md shadow-amber-500/20"
                  >
                    {isSaving ? 'Saving...' : 'Save Residency & Tax Settings'}
                  </button>
                </div>
              </div>

              {/* Analytics Assessment Evidence Card */}
              {detail.assessments && detail.assessments.length > 0 && (
                <div className="rounded-xl bg-slate-800/40 border border-slate-700/80 p-5 space-y-3">
                  <h3 className="text-sm font-bold text-amber-400 uppercase tracking-wider flex items-center gap-2">
                    <ShieldCheck className="w-4 h-4" /> Stay Assessments & Mathematical Evidence
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {detail.assessments.map((a) => (
                      <div
                        key={a.id}
                        className={`p-4 rounded-lg border ${
                          a.mode === 'continuous_stay'
                            ? 'bg-amber-500/10 border-amber-500/30 text-amber-100'
                            : 'bg-blue-500/10 border-blue-500/30 text-blue-100'
                        }`}
                      >
                        <div className="flex items-center justify-between font-bold text-sm">
                          <span>{a.mode === 'continuous_stay' ? 'Mode A: Continuous Stay' : 'Mode B: Repeated Appearances'}</span>
                          <span className="text-xs px-2 py-0.5 rounded bg-slate-900/80 border border-slate-700 font-mono">
                            {a.verification_status}
                          </span>
                        </div>
                        <div className="mt-2 text-xs space-y-1">
                          <div>
                            <span className="text-slate-400">Duration / Count: </span>
                            <span className="font-bold text-white">
                              {a.mode === 'continuous_stay' ? `${a.stay_duration_days} consecutive calendar days` : `${a.reporting_dates_count} distinct reporting dates`}
                            </span>
                          </div>
                          <div>
                            <span className="text-slate-400">Date Span: </span>
                            <span className="text-slate-200">{a.first_date} to {a.last_date}</span>
                          </div>
                          <div>
                            <span className="text-slate-400">Rooms: </span>
                            <span className="font-mono text-slate-200">{a.rooms.join(', ') || 'N/A'}</span>
                          </div>
                          <div>
                            <span className="text-slate-400">Evidence: </span>
                            <span className="text-slate-300 italic">{a.evidence_source}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Chronological Departure Records Timeline */}
              <div className="space-y-3">
                <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-amber-400" />
                  Chronological Report Records Timeline ({detail.timeline.length})
                </h3>

                <div className="space-y-3">
                  {detail.timeline.map((item, idx) => (
                    <div
                      key={item.record_id}
                      className="p-4 rounded-xl bg-slate-800/60 border border-slate-700/60 hover:border-slate-600 transition-all flex flex-col md:flex-row md:items-center justify-between gap-4"
                    >
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-lg bg-slate-900 border border-slate-700 flex items-center justify-center font-bold text-amber-400 text-xs shrink-0 mt-0.5">
                          {idx + 1}
                        </div>
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-900 text-slate-200 border border-slate-700">
                              Report: {item.report_date}
                            </span>
                            <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                              Room {item.room_number || 'N/A'}
                            </span>
                            <span className="text-xs font-mono text-slate-400">
                              Conf: #{item.confirmation_number || 'None'}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                              {item.status}
                            </span>
                          </div>

                          <div className="text-xs text-slate-300 flex flex-wrap items-center gap-x-4 gap-y-1 pt-1">
                            <span>
                              <span className="text-slate-400">Check-in:</span> {item.check_in_date || 'N/A'}
                            </span>
                            <span>
                              <span className="text-slate-400">Nights:</span> <strong className="text-white">{item.number_of_nights ?? 'N/A'}</strong>
                            </span>
                            <span>
                              <span className="text-slate-400">Calc Departure:</span> {item.calculated_departure_date || 'N/A'}
                            </span>
                            {item.actual_departed_time && (
                              <span>
                                <span className="text-slate-400">Departed:</span> {item.actual_departed_time}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        <div className="text-xs text-slate-400">
                          Source: Page {item.source_page}, Row {item.source_row_index}
                        </div>
                        <div className="text-[11px] text-slate-400 mt-0.5">
                          File: {item.report_file}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Identity Reconciliation Match History */}
              {detail.matches && detail.matches.length > 0 && (
                <div className="space-y-2">
                  <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                    <Hash className="w-4 h-4 text-amber-400" /> Identity Match Audit History
                  </h3>
                  <div className="border border-slate-800 rounded-xl overflow-hidden text-xs">
                    <table className="w-full text-left">
                      <thead className="bg-slate-950/80 text-slate-400 font-semibold border-b border-slate-800">
                        <tr>
                          <th className="py-2.5 px-3">Date (NY Time)</th>
                          <th className="py-2.5 px-3">Match Type</th>
                          <th className="py-2.5 px-3">Confidence</th>
                          <th className="py-2.5 px-3">Status</th>
                          <th className="py-2.5 px-3">Review Notes</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60 bg-slate-900/60 text-slate-300">
                        {detail.matches.map((m) => (
                          <tr key={m.id}>
                            <td className="py-2 px-3 font-mono text-[11px] text-slate-400">{formatNYDateTime(m.created_at)}</td>
                            <td className="py-2 px-3 font-mono text-amber-300">{m.match_type}</td>
                            <td className="py-2 px-3">{(m.confidence_score * 100).toFixed(0)}%</td>
                            <td className="py-2 px-3">
                              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-200">
                                {m.status}
                              </span>
                            </td>
                            <td className="py-2 px-3 text-slate-400">{m.review_notes || 'Automatic match'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 flex justify-end bg-slate-950/60">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
