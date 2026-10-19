import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  GitMerge,
  Split,
  RefreshCw,
  ShieldCheck,
  User,
  Home,
  Calendar
} from 'lucide-react';
import { api } from '../services/api';
import { ReviewQueueData } from '../types';

export const ReviewQueuePage: React.FC = () => {
  const [data, setData] = useState<ReviewQueueData | null>(null);
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState<number | null>(null);

  const loadQueue = () => {
    setLoading(true);
    api.getReviewQueue()
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleConfirmMatch = async (matchId: number) => {
    setProcessingId(matchId);
    try {
      await api.confirmIdentityMatch(matchId);
      loadQueue();
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
      loadQueue();
    } catch (err: any) {
      alert(err.message || 'Failed to split identity');
    } finally {
      setProcessingId(null);
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

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
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
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-amber-400' : ''}`} />
        </button>
      </div>

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
          <div className="flex items-center gap-2 text-sm font-bold text-amber-400 uppercase tracking-wider">
            <GitMerge className="w-4 h-4" />
            <span>Uncertain Guest Identity Matches ({data.proposed_matches.length})</span>
          </div>

          <div className="space-y-4">
            {data.proposed_matches.map((m) => (
              <div
                key={m.match_id}
                className="p-5 rounded-xl bg-slate-900 border border-slate-800 space-y-4 hover:border-slate-700 transition-all shadow-md"
              >
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-white">Match Type:</span>
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
                      {m.match_type}
                    </span>
                    <span className="text-xs text-slate-400">Confidence: {(m.confidence_score * 100).toFixed(0)}%</span>
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
                    <div className="text-slate-300">Room: <strong className="text-amber-400 font-mono">{m.record?.room_number || 'N/A'}</strong></div>
                    <div className="text-slate-300">Conf: <strong className="font-mono text-slate-200">#{m.record?.confirmation_number || 'None'}</strong></div>
                    <div className="text-slate-400">Report Date: {m.record?.report_date}</div>
                  </div>

                  {/* Right: Candidate Identity */}
                  <div className="p-3.5 rounded-lg bg-slate-800/60 border border-slate-700/60 space-y-1.5">
                    <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                      Existing Candidate Profile
                    </div>
                    <div className="text-sm font-bold text-white">{m.candidate_identity?.name}</div>
                    <div className="text-slate-300">Profile ID: <strong className="text-slate-200 font-mono">#{m.candidate_identity?.id}</strong></div>
                    <div className="text-slate-300">Current Status: <span className="font-bold text-emerald-400">{m.candidate_identity?.status}</span></div>
                    <div className="text-slate-400">Same name observed across different rooms or dates.</div>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-end gap-3 pt-2">
                  <button
                    onClick={() => handleRejectMatch(m.match_id)}
                    disabled={processingId === m.match_id}
                    className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-all border border-slate-700"
                  >
                    <Split className="w-3.5 h-3.5 text-rose-400" />
                    <span>Split into Separate Person</span>
                  </button>

                  <button
                    onClick={() => handleConfirmMatch(m.match_id)}
                    disabled={processingId === m.match_id}
                    className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-all shadow-md shadow-amber-500/20"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Confirm Merge (Same Guest)</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
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
                    Stay Duration: <strong className="text-white font-mono">{a.stay_duration_days} Days</strong> • Rooms: <span className="font-mono">{a.rooms.join(', ')}</span>
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
    </div>
  );
};
