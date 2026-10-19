import React, { useState, useEffect } from 'react';
import { History, Download, Trash2, Calendar, FileText, CheckCircle2, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { ReportItem } from '../types';

export const ReportHistoryPage: React.FC = () => {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const loadReports = () => {
    setLoading(true);
    api.getReports()
      .then((res) => setReports(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadReports();
  }, []);

  const handleDelete = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this report? This will remove its guest records and recalculate the rolling window.')) {
      return;
    }
    setDeletingId(id);
    try {
      await api.deleteReport(id);
      loadReports();
    } catch (err: any) {
      alert(err.message || 'Failed to delete report');
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <History className="w-6 h-6 text-amber-400" /> Report History ({reports.length})
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Historical archive of all uploaded daily reports. Original PDFs are stored permanently.
          </p>
        </div>

        <button
          onClick={loadReports}
          className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          title="Refresh"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-amber-400' : ''}`} />
        </button>
      </div>

      <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Filename</th>
                <th className="py-3 px-4">Reporting Date</th>
                <th className="py-3 px-4">Property</th>
                <th className="py-3 px-4">Records</th>
                <th className="py-3 px-4">File Size</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Imported At</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={8} className="py-10 text-center text-slate-500 animate-pulse">
                    Loading report archive...
                  </td>
                </tr>
              ) : reports.length > 0 ? (
                reports.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-4 font-mono font-bold text-white flex items-center gap-2">
                      <FileText className="w-4 h-4 text-amber-400 shrink-0" />
                      <span>{r.original_filename}</span>
                    </td>
                    <td className="py-3 px-4 font-mono text-amber-300 font-semibold">{r.report_date}</td>
                    <td className="py-3 px-4 text-slate-300">{r.property_name}</td>
                    <td className="py-3 px-4 font-mono text-white font-bold">{r.valid_rows_count} valid</td>
                    <td className="py-3 px-4 font-mono text-slate-400">{(r.file_size_bytes / 1024).toFixed(1)} KB</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {r.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-400">{new Date(r.created_at).toLocaleString()}</td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <a
                          href={api.getDownloadUrl(r.id)}
                          download={r.original_filename}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-amber-400 transition-colors"
                          title="Download original PDF"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                        <button
                          onClick={() => handleDelete(r.id)}
                          disabled={deletingId === r.id}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-rose-400 transition-colors"
                          title="Delete report"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500 text-xs">
                    No reports imported yet.
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
