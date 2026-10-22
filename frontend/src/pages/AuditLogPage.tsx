import React, { useState, useEffect } from 'react';
import { ShieldCheck, Search, Filter, RefreshCw, Clock } from 'lucide-react';
import { api } from '../services/api';
import { AuditLogItem } from '../types';
import { formatNYDateTime } from '../utils/dateUtils';

export const AuditLogPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [actionFilter, setActionFilter] = useState('');

  const loadLogs = () => {
    setLoading(true);
    api.getAuditLogs({
      action: actionFilter || undefined,
      page: 1,
      page_size: 100,
    })
      .then((res) => {
        setLogs(res.items);
        setTotal(res.total);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadLogs();
  }, [actionFilter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <ShieldCheck className="w-6 h-6 text-amber-400" /> Audit Log ({total})
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Tamper-evident trail of report uploads, identity merges, stay verifications, and settings changes.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            className="bg-slate-900 border border-slate-800 focus:border-amber-400 rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none"
          >
            <option value="">All Audit Actions</option>
            <option value="commit_import">Report Import</option>
            <option value="upload_preview">Upload Preview</option>
            <option value="replace_report">Report Replacement</option>
            <option value="delete_report">Report Deletion</option>
            <option value="confirm_match">Identity Merge Confirmation</option>
            <option value="split_guest_identity">Identity Split</option>
            <option value="update_settings">Settings Modification</option>
          </select>

          <button
            onClick={loadLogs}
            className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-amber-400' : ''}`} />
          </button>
        </div>
      </div>

      <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Timestamp (NY Time)</th>
                <th className="py-3 px-4">Operator / User</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Entity</th>
                <th className="py-3 px-4">Audit Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={5} className="py-10 text-center text-slate-500 animate-pulse">
                    Loading audit trail...
                  </td>
                </tr>
              ) : logs.length > 0 ? (
                logs.map((l) => (
                  <tr key={l.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 font-mono text-slate-300 text-xs">{formatNYDateTime(l.created_at)}</td>
                    <td className="py-3 px-4 font-semibold text-white">{l.user_email}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                        {l.action}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-300">
                      {l.entity_type} {l.entity_id ? `#${l.entity_id}` : ''}
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-400 max-w-md truncate">
                      {JSON.stringify(l.details)}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-slate-500 text-xs">
                    No audit records found.
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
