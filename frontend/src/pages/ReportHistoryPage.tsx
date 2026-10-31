import React, { useState, useEffect } from 'react';
import { History, Trash2, FileText, RefreshCw, Loader2, FileSpreadsheet } from 'lucide-react';
import { api } from '../services/api';
import { ReportItem } from '../types';
import { formatNYDateTime, formatMMDDYYYY } from '../utils/dateUtils';
import { useProperty } from '../context/PropertyContext';

export const ReportHistoryPage: React.FC = () => {
  const { currentPropertyId, currentProperty } = useProperty();
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [downloadingId, setDownloadingId] = useState<number | null>(null);

  const loadReports = () => {
    setLoading(true);
    api.getReports(currentPropertyId)
      .then((res) => setReports(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadReports();
  }, [currentPropertyId]);

  const handleDownloadExcel = async (report: ReportItem) => {
    setDownloadingId(report.id);
    try {
      await api.downloadReportExcel(report.id, report.original_filename);
    } catch (err: any) {
      alert(err.message || 'Failed to download report Excel file');
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this report? This will remove all its guest records and recalculate stay analytics and rolling windows.')) {
      return;
    }
    setDeletingId(id);
    try {
      await api.deleteReport(id);
      loadReports();
      window.dispatchEvent(new CustomEvent('staytrack:data_changed'));
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
          <p className="text-xs text-slate-400 mt-1 flex items-center gap-2">
            <span>Historical archive of imported report data for</span>
            <span className="font-bold text-amber-400">{currentProperty?.name} (#{currentProperty?.property_code})</span>
            {loading && <Loader2 className="w-3.5 h-3.5 animate-spin text-amber-400" />}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={loadReports}
            className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer border border-slate-700"
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
                <th className="py-3 px-4">Report / Source File</th>
                <th className="py-3 px-4">Reporting Date & PMS Run</th>
                <th className="py-3 px-4">Property</th>
                <th className="py-3 px-4">Extracted Records</th>
                <th className="py-3 px-4">File Size</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Imported At (NY Time)</th>
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
                    <td className="py-3 px-4">
                      <div className="font-mono text-amber-300 font-semibold">{formatMMDDYYYY(r.report_date)}</div>
                      {r.report_run_datetime && (
                        <div className="text-[11px] text-slate-400 font-mono mt-0.5 flex items-center gap-1" title="PMS Report Run Date & Time (Local Eastern Time)">
                          <span className="text-slate-500 font-normal">PMS:</span>
                          <span className="text-slate-300">{r.report_run_datetime}</span>
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 text-slate-300">{r.property_name}</td>
                    <td className="py-3 px-4 font-mono text-white font-bold">{r.valid_rows_count} valid records</td>
                    <td className="py-3 px-4 font-mono text-slate-400">{(r.file_size_bytes / 1024).toFixed(1)} KB</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        {r.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-300 text-xs">
                      {formatNYDateTime(r.created_at)}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => handleDownloadExcel(r)}
                          disabled={downloadingId === r.id}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-emerald-400 transition-colors cursor-pointer flex items-center gap-1"
                          title="Download Excel Report Data (.xlsx)"
                        >
                          {downloadingId === r.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-400" />
                          ) : (
                            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-400" />
                          )}
                        </button>
                        <button
                          onClick={() => handleDelete(r.id)}
                          disabled={deletingId === r.id}
                          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-rose-400 transition-colors cursor-pointer"
                          title="Delete report and its data"
                        >
                          {deletingId === r.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin text-rose-400" />
                          ) : (
                            <Trash2 className="w-3.5 h-3.5" />
                          )}
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
