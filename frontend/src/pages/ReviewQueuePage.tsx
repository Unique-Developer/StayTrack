import React, { useState, useEffect, useRef } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  GitMerge,
  Split,
  RefreshCw,
  ShieldCheck,
  Search,
  X
} from 'lucide-react';
import { api } from '../services/api';
import { ReviewQueueData } from '../types';

export const ReviewQueuePage: React.FC = () => {
  const [data, setData] = useState<ReviewQueueData | null>(null);
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);

  // Multi-selection state
  const [selectedMatchIds, setSelectedMatchIds] = useState<Set<number>>(new Set());
  const [searchTerm, setSearchTerm] = useState('');
  const [batchModal, setBatchModal] = useState<{
    isOpen: boolean;
    action: 'confirm' | 'reject';
  } | null>(null);
  const [batchProcessing, setBatchProcessing] = useState(false);
  const [banner, setBanner] = useState<{
    type: 'success' | 'error';
    message: string;
  } | null>(null);

  const masterCheckboxRef = useRef<HTMLInputElement | null>(null);

  const loadQueue = () => {
    setLoading(true);
    api.getReviewQueue()
      .then((res) => {
        setData(res);
        // Clean up selections that might not be in the queue anymore
        const currentIds = new Set((res.proposed_matches || []).map((m) => m.match_id));
        setSelectedMatchIds((prev) => {
          const next = new Set<number>();
          prev.forEach((id) => {
            if (currentIds.has(id)) next.add(id);
          });
          return next;
        });
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadQueue();
  }, []);

  // Filter proposed matches based on search term
  const filteredMatches = (data?.proposed_matches || []).filter((m) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    const guestName = m.record?.guest_name?.toLowerCase() || '';
    const candName = m.candidate_identity?.name?.toLowerCase() || '';
    const room = m.record?.room_number?.toLowerCase() || '';
    const conf = m.record?.confirmation_number?.toLowerCase() || '';
    const matchType = m.match_type?.toLowerCase() || '';
    return (
      guestName.includes(term) ||
      candName.includes(term) ||
      room.includes(term) ||
      conf.includes(term) ||
      matchType.includes(term)
    );
  });

  const visibleSelectedCount = filteredMatches.filter((m) => selectedMatchIds.has(m.match_id)).length;
  const isAllVisibleSelected = filteredMatches.length > 0 && visibleSelectedCount === filteredMatches.length;
  const isSomeVisibleSelected = visibleSelectedCount > 0 && !isAllVisibleSelected;

  // Sync master checkbox indeterminate property
  useEffect(() => {
    if (masterCheckboxRef.current) {
      masterCheckboxRef.current.indeterminate = isSomeVisibleSelected;
    }
  }, [isSomeVisibleSelected]);

  // Toggle selection for a single match
  const toggleMatchSelection = (matchId: number) => {
    setSelectedMatchIds((prev) => {
      const next = new Set(prev);
      if (next.has(matchId)) {
        next.delete(matchId);
      } else {
        next.add(matchId);
      }
      return next;
    });
  };

  // Toggle selection for all visible matches
  const handleToggleSelectAllVisible = () => {
    if (isAllVisibleSelected) {
      setSelectedMatchIds((prev) => {
        const next = new Set(prev);
        filteredMatches.forEach((m) => next.delete(m.match_id));
        return next;
      });
    } else {
      setSelectedMatchIds((prev) => {
        const next = new Set(prev);
        filteredMatches.forEach((m) => next.add(m.match_id));
        return next;
      });
    }
  };

  // Select all total matches
  const handleSelectAllTotal = () => {
    if (!data?.proposed_matches) return;
    const next = new Set<number>();
    data.proposed_matches.forEach((m) => next.add(m.match_id));
    setSelectedMatchIds(next);
  };

  // Clear all selections
  const clearSelection = () => {
    setSelectedMatchIds(new Set());
  };

  // Individual Actions
  const handleConfirmMatch = async (matchId: number) => {
    setProcessingId(matchId);
    try {
      await api.confirmIdentityMatch(matchId);
      setSelectedMatchIds((prev) => {
        const next = new Set(prev);
        next.delete(matchId);
        return next;
      });
      loadQueue();
      setBanner({
        type: 'success',
        message: 'Identity match confirmed and customer profiles merged successfully.'
      });
    } catch (err: any) {
      alert(err.message || 'Failed to confirm match');
    } finally {
      setProcessingId(null);
    }
  };

  const handleRejectMatch = async (matchId: number) => {
    setProcessingId(matchId);
    try {
      await api.rejectIdentityMatch(matchId);
      setSelectedMatchIds((prev) => {
        const next = new Set(prev);
        next.delete(matchId);
        return next;
      });
      loadQueue();
      setBanner({
        type: 'success',
        message: 'Identity split successfully into separate customer profile.'
      });
    } catch (err: any) {
      alert(err.message || 'Failed to split identity');
    } finally {
      setProcessingId(null);
    }
  };

  // Batch Actions
  const handleBatchConfirm = async () => {
    if (selectedMatchIds.size === 0) return;
    setBatchProcessing(true);
    try {
      const ids = Array.from(selectedMatchIds);
      const res = await api.batchConfirmMatches(ids);
      setBanner({
        type: 'success',
        message: res.message || `Successfully merged ${ids.length} customer matches.`
      });
      setSelectedMatchIds(new Set());
      setBatchModal(null);
      loadQueue();
    } catch (err: any) {
      setBanner({
        type: 'error',
        message: err.message || 'Failed to batch merge matches.'
      });
    } finally {
      setBatchProcessing(false);
    }
  };

  const handleBatchReject = async () => {
    if (selectedMatchIds.size === 0) return;
    setBatchProcessing(true);
    try {
      const ids = Array.from(selectedMatchIds);
      const res = await api.batchRejectMatches(ids);
      setBanner({
        type: 'success',
        message: res.message || `Successfully split ${ids.length} records into separate customer profiles.`
      });
      setSelectedMatchIds(new Set());
      setBatchModal(null);
      loadQueue();
    } catch (err: any) {
      setBanner({
        type: 'error',
        message: err.message || 'Failed to batch split matches.'
      });
    } finally {
      setBatchProcessing(false);
    }
  };

  const handleVerifyAssessment = async (assessmentId: number, action: 'verify' | 'reject') => {
    setProcessingId(assessmentId);
    try {
      await api.verifyAssessment(assessmentId, action, 'Manual verification by motel operator');
      loadQueue();
    } catch (err: any) {
      alert(err.message || 'Failed to update assessment');
    } finally {
      setProcessingId(null);
    }
  };

  const totalPending = (data?.pending_matches_count || 0) + (data?.uncertain_assessments_count || 0);

  // Selected items list for confirmation modal
  const selectedMatchesList = (data?.proposed_matches || []).filter((m) =>
    selectedMatchIds.has(m.match_id)
  );

  return (
    <div className="space-y-6 max-w-5xl mx-auto pb-24">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <AlertTriangle className="w-6 h-6 text-amber-400" /> Review Queue ({totalPending})
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Resolve ambiguous identity matches and verify uncertain continuous stays.
          </p>
        </div>

        <button
          onClick={loadQueue}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          title="Refresh Queue"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-amber-400' : ''}`} />
        </button>
      </div>

      {/* Dismissible Feedback Banner */}
      {banner && (
        <div
          className={`p-4 rounded-xl border flex items-center justify-between gap-3 text-xs font-semibold animate-in fade-in duration-200 ${
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
            className="p-1 rounded hover:bg-slate-800/60 text-slate-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {totalPending === 0 && !loading && (
        <div className="py-16 text-center rounded-2xl bg-slate-900 border border-slate-800 p-8 space-y-3">
          <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h2 className="text-base font-bold text-white">Review Queue is Clear!</h2>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            All guest identities and continuous stay assessments have been reconciled with high confidence.
          </p>
        </div>
      )}

      {/* Section 1: Guest Identity Reconciliation Matches */}
      {data?.proposed_matches && data.proposed_matches.length > 0 && (
        <div className="space-y-4">
          {/* Section Header with Quick Actions */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
            <div className="flex items-center gap-2 text-sm font-bold text-amber-400 uppercase tracking-wider">
              <GitMerge className="w-4 h-4" />
              <span>Uncertain Guest Identity Matches ({data.proposed_matches.length})</span>
            </div>

            {/* Quick bulk action buttons in header if any selected */}
            {selectedMatchIds.size > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-xs px-2.5 py-1 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold font-mono">
                  {selectedMatchIds.size} Selected
                </span>
                <button
                  onClick={() => setBatchModal({ isOpen: true, action: 'confirm' })}
                  disabled={batchProcessing}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-all shadow-md shadow-amber-500/20"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Merge Selected ({selectedMatchIds.size})</span>
                </button>
              </div>
            )}
          </div>

          {/* Multi-Selection Toolbar & Search */}
          <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 shadow-sm">
            {/* Left: Master Checkbox & Selection Controls */}
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <label className="flex items-center gap-2.5 cursor-pointer select-none text-slate-300 hover:text-white font-medium py-1 px-1.5 rounded hover:bg-slate-800/60 transition-colors">
                <input
                  ref={masterCheckboxRef}
                  type="checkbox"
                  checked={isAllVisibleSelected}
                  onChange={handleToggleSelectAllVisible}
                  className="w-4 h-4 rounded text-amber-500 bg-slate-950 border-slate-700 focus:ring-amber-400 focus:ring-offset-slate-900 cursor-pointer accent-amber-500"
                />
                <span>
                  {isAllVisibleSelected
                    ? 'Deselect All Visible'
                    : `Select All Visible (${filteredMatches.length})`}
                </span>
              </label>

              {data.proposed_matches.length > filteredMatches.length && (
                <button
                  onClick={handleSelectAllTotal}
                  className="text-amber-400 hover:text-amber-300 underline underline-offset-2 text-xs transition-colors"
                >
                  Select all {data.proposed_matches.length} total
                </button>
              )}

              {selectedMatchIds.size > 0 && (
                <button
                  onClick={clearSelection}
                  className="text-slate-400 hover:text-slate-200 text-xs transition-colors"
                >
                  Clear Selection
                </button>
              )}
            </div>

            {/* Right: Search Filter */}
            <div className="relative min-w-[240px]">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Filter by name, room, or conf #..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-9 pr-8 py-1.5 bg-slate-950/80 border border-slate-800 focus:border-amber-400 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none transition-colors"
              />
              {searchTerm && (
                <button
                  type="button"
                  onClick={() => setSearchTerm('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Matches List */}
          {filteredMatches.length === 0 ? (
            <div className="py-8 text-center text-xs text-slate-500 bg-slate-900/40 rounded-xl border border-slate-800">
              No identity matches match your search criteria "{searchTerm}".
            </div>
          ) : (
            <div className="space-y-4">
              {filteredMatches.map((m) => {
                const isSelected = selectedMatchIds.has(m.match_id);

                return (
                  <div
                    key={m.match_id}
                    className={`p-5 rounded-xl transition-all shadow-md space-y-4 border ${
                      isSelected
                        ? 'bg-slate-900 border-amber-500/50 ring-1 ring-amber-500/30'
                        : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                    }`}
                  >
                    {/* Top Row: Checkbox + Match Info */}
                    <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                      <div className="flex items-center gap-3">
                        {/* Multi-Selection Checkbox */}
                        <label className="flex items-center gap-2 cursor-pointer select-none">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleMatchSelection(m.match_id)}
                            className="w-4 h-4 rounded text-amber-500 bg-slate-950 border-slate-700 focus:ring-amber-400 focus:ring-offset-slate-900 cursor-pointer accent-amber-500"
                          />
                          <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                            Select
                          </span>
                        </label>

                        <div className="h-4 w-px bg-slate-800" />

                        <div className="flex items-center gap-2">
                          <span className="text-xs font-bold text-white">Match Type:</span>
                          <span className="font-mono text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                            {m.match_type}
                          </span>
                          <span className="text-xs text-slate-400">
                            Confidence: {(m.confidence_score * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>

                      <div className="text-xs text-slate-400 italic">{m.review_notes}</div>
                    </div>

                    {/* Comparison Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                      {/* Left: Source Record */}
                      <div className="p-3.5 rounded-lg bg-slate-800/60 border border-slate-700/60 space-y-1.5">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                          Incoming Report Record
                        </div>
                        <div className="text-sm font-bold text-white">{m.record?.guest_name}</div>
                        <div className="text-slate-300">
                          Room:{' '}
                          <strong className="text-amber-400 font-mono">
                            {m.record?.room_number || 'N/A'}
                          </strong>
                        </div>
                        <div className="text-slate-300">
                          Conf:{' '}
                          <strong className="font-mono text-slate-200">
                            #{m.record?.confirmation_number || 'None'}
                          </strong>
                        </div>
                        <div className="text-slate-400">Report Date: {m.record?.report_date}</div>
                      </div>

                      {/* Right: Candidate Identity */}
                      <div className="p-3.5 rounded-lg bg-slate-800/60 border border-slate-700/60 space-y-1.5">
                        <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                          Existing Candidate Profile
                        </div>
                        <div className="text-sm font-bold text-white">
                          {m.candidate_identity?.name}
                        </div>
                        <div className="text-slate-300">
                          Profile ID:{' '}
                          <strong className="text-slate-200 font-mono">
                            #{m.candidate_identity?.id}
                          </strong>
                        </div>
                        <div className="text-slate-300">
                          Current Status:{' '}
                          <span className="font-bold text-emerald-400">
                            {m.candidate_identity?.status}
                          </span>
                        </div>
                        <div className="text-slate-400">
                          Same name observed across different rooms or dates.
                        </div>
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center justify-end gap-3 pt-2">
                      <button
                        onClick={() => handleRejectMatch(m.match_id)}
                        disabled={processingId === m.match_id || batchProcessing}
                        className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-all border border-slate-700"
                      >
                        <Split className="w-3.5 h-3.5 text-rose-400" />
                        <span>Split into Separate Person</span>
                      </button>

                      <button
                        onClick={() => handleConfirmMatch(m.match_id)}
                        disabled={processingId === m.match_id || batchProcessing}
                        className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-all shadow-md shadow-amber-500/20"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        <span>Confirm Merge (Same Guest)</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Section 2: Uncertain Stay Assessments */}
      {data?.uncertain_assessments && data.uncertain_assessments.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm font-bold text-amber-400 uppercase tracking-wider">
            <ShieldCheck className="w-4 h-4" />
            <span>Stay Assessments Needing Verification ({data.uncertain_assessments.length})</span>
          </div>

          <div className="space-y-4">
            {data.uncertain_assessments.map((a) => (
              <div
                key={a.assessment_id}
                className="p-5 rounded-xl bg-slate-900 border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:border-slate-700 transition-all"
              >
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-white">{a.guest_name}</span>
                    <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-bold">
                      {a.mode === 'continuous_stay' ? 'Continuous Stay' : 'Repeated Appearances'}
                    </span>
                  </div>
                  <div className="text-slate-300">
                    Stay Duration:{' '}
                    <strong className="text-white font-mono">{a.stay_duration_days} Days</strong> •
                    Rooms: <span className="font-mono">{a.rooms.join(', ')}</span>
                  </div>
                  <div className="text-slate-400 italic">
                    Reason: {a.evidence_source} • {a.notes}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={() => handleVerifyAssessment(a.assessment_id, 'reject')}
                    disabled={processingId === a.assessment_id}
                    className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold border border-slate-700"
                  >
                    Reject Stay
                  </button>
                  <button
                    onClick={() => handleVerifyAssessment(a.assessment_id, 'verify')}
                    disabled={processingId === a.assessment_id}
                    className="px-3.5 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold shadow-md shadow-emerald-500/20"
                  >
                    Verify Stay
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Floating Sticky Bottom Toolbar (Appears when items are selected) */}
      {selectedMatchIds.size > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 bg-slate-900/95 backdrop-blur-md border border-amber-500/40 shadow-2xl shadow-black/80 rounded-2xl px-5 py-3 flex flex-wrap items-center justify-between gap-4 text-xs animate-in slide-in-from-bottom-5 duration-200">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
            <span className="font-bold text-white">
              <strong className="text-amber-400 font-mono text-sm">{selectedMatchIds.size}</strong>{' '}
              customer match{selectedMatchIds.size > 1 ? 'es' : ''} selected
            </span>
          </div>

          <div className="h-4 w-px bg-slate-700 hidden sm:block" />

          <div className="flex items-center gap-2.5">
            <button
              onClick={clearSelection}
              disabled={batchProcessing}
              className="text-slate-400 hover:text-white px-2 py-1 text-xs transition-colors hover:underline"
            >
              Deselect All
            </button>

            <button
              onClick={() => setBatchModal({ isOpen: true, action: 'reject' })}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition-all border border-slate-700"
            >
              <Split className="w-3.5 h-3.5 text-rose-400" />
              <span>Split Selected</span>
            </button>

            <button
              onClick={() => setBatchModal({ isOpen: true, action: 'confirm' })}
              disabled={batchProcessing}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black transition-all shadow-lg shadow-amber-500/30"
            >
              <GitMerge className="w-4 h-4" />
              <span>Confirm Merge ({selectedMatchIds.size})</span>
            </button>
          </div>
        </div>
      )}

      {/* Confirmation Modal for Batch Merge / Split */}
      {batchModal?.isOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
          <div className="bg-slate-900 border border-slate-700 w-full max-w-lg rounded-2xl shadow-2xl p-6 space-y-5 animate-in zoom-in-95 duration-150">
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold ${
                    batchModal.action === 'confirm'
                      ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                      : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                  }`}
                >
                  {batchModal.action === 'confirm' ? (
                    <GitMerge className="w-5 h-5" />
                  ) : (
                    <Split className="w-5 h-5" />
                  )}
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">
                    {batchModal.action === 'confirm'
                      ? `Confirm Batch Merge (${selectedMatchIds.size} Customers)`
                      : `Confirm Batch Split (${selectedMatchIds.size} Records)`}
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    {batchModal.action === 'confirm'
                      ? 'Merge selected records into existing candidate profiles'
                      : 'Separate selected records into independent profiles'}
                  </p>
                </div>
              </div>

              {!batchProcessing && (
                <button
                  onClick={() => setBatchModal(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              {batchModal.action === 'confirm' ? (
                <>
                  You are about to merge <strong>{selectedMatchIds.size}</strong> incoming records into
                  their respective candidate guest profiles. All reservation histories, continuous stay
                  durations, and reporting statistics will be recomputed automatically.
                </>
              ) : (
                <>
                  You are about to split <strong>{selectedMatchIds.size}</strong> records into separate,
                  distinct guest profiles. They will no longer be linked to candidate profiles.
                </>
              )}
            </p>

            {/* Selected Guests Summary Preview */}
            <div className="space-y-1.5">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Selected Records ({selectedMatchIds.size})
              </div>
              <div className="max-h-48 overflow-y-auto rounded-lg bg-slate-950/80 border border-slate-800 p-2.5 divide-y divide-slate-800/60 text-xs">
                {selectedMatchesList.slice(0, 10).map((m) => (
                  <div key={m.match_id} className="py-1.5 flex items-center justify-between gap-2">
                    <span className="font-bold text-white truncate max-w-[200px]">
                      {m.record?.guest_name}
                    </span>
                    <span className="text-slate-400 font-mono text-[11px] shrink-0">
                      Rm {m.record?.room_number || 'N/A'} → Profile #{m.candidate_identity?.id}
                    </span>
                  </div>
                ))}
                {selectedMatchesList.length > 10 && (
                  <div className="pt-2 text-center text-slate-500 text-[11px] italic">
                    ...and {selectedMatchesList.length - 10} more records
                  </div>
                )}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setBatchModal(null)}
                disabled={batchProcessing}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition-colors disabled:opacity-50"
              >
                Cancel
              </button>

              <button
                type="button"
                onClick={batchModal.action === 'confirm' ? handleBatchConfirm : handleBatchReject}
                disabled={batchProcessing}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-bold transition-all shadow-md ${
                  batchModal.action === 'confirm'
                    ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 shadow-amber-500/20'
                    : 'bg-rose-500 hover:bg-rose-400 text-white shadow-rose-500/20'
                } disabled:opacity-50`}
              >
                {batchProcessing && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>
                  {batchProcessing
                    ? 'Processing...'
                    : batchModal.action === 'confirm'
                    ? `Confirm & Merge (${selectedMatchIds.size})`
                    : `Confirm & Split (${selectedMatchIds.size})`}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};