import React, { useState, useEffect } from 'react';
import { FileText, Search, Download, ChevronRight, Filter, Calendar } from 'lucide-react';
import { api } from '../services/api';
import { GuestRecordItem } from '../types';
import { GuestDetailModal } from '../components/GuestDetailModal';

export const AllRecordsPage: React.FC = () => {
  const [records, setRecords] = useState<GuestRecordItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [reportDate, setReportDate] = useState('');
  const [selectedGuestId, setSelectedGuestId] = useState<number | null>(null);

  const loadRecords = () => {
    setLoading(true);
    api.getAllRecords({
      search: search || undefined,
      report_date: reportDate || undefined,
      page: 1,
      page_size: 200,
    })
      .then((res) => {
        setRecords(res.items);
        setTotal(res.total);
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadRecords();
  }, [reportDate]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadRecords();
  };

  const handleExport = () => {
    const url = api.getAllRecordsExportUrl({
      search: search || undefined,
      report_date: reportDate || undefined,
    });
    window.open(url, '_blank');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
            <FileText className="w-6 h-6 text-amber-400" /> All Guest Records ({total})
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Every departure record extracted and normalized from historical PDF reports.
          </p>
        </div>

        <button
          onClick={handleExport}
          className="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-xs font-semibold transition-all shadow-sm"
        >
          <Download className="w-4 h-4 text-amber-400" />
          <span>Export All CSV</span>
        </button>
      </div>

      {/* Filter Bar */}
      <form onSubmit={handleSearch} className="flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by guest name, room number, or confirmation #..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-900 border border-slate-800 focus:border-amber-400 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs">
          <Calendar className="w-3.5 h-3.5 text-amber-400" />
          <span className="text-slate-400">Date:</span>
          <input
            type="date"
            value={reportDate}
            onChange={(e) => setReportDate(e.target.value)}
            className="bg-transparent text-white font-mono focus:outline-none"
          />
          {reportDate && (
            <button
              type="button"
              onClick={() => setReportDate('')}
              className="text-slate-500 hover:text-slate-300 text-xs font-bold"
            >
              ×
            </button>
          )}
        </div>

        <button
          type="submit"
          className="px-4 py-2 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-lg text-xs transition-colors"
        >
          Search
        </button>
      </form>

      {/* Table */}
      <div className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 font-semibold uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Report Date</th>
                <th className="py-3 px-4">Room</th>
                <th className="py-3 px-4">Guest Name</th>
                <th className="py-3 px-4">Confirmation #</th>
                <th className="py-3 px-4">Check-In</th>
                <th className="py-3 px-4">Nights</th>
                <th className="py-3 px-4">Calc Departure</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Departed Time</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-300">
              {loading ? (
                <tr>
                  <td colSpan={10} className="py-10 text-center text-slate-500 animate-pulse">
                    Loading records...
                  </td>
                </tr>
              ) : records.length > 0 ? (
                records.map((r) => (
                  <tr
                    key={r.id}
                    onClick={() => r.guest_identity_id && setSelectedGuestId(r.guest_identity_id)}
                    className="hover:bg-slate-800/40 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4 font-mono text-amber-300 font-semibold">{r.report_date}</td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded bg-slate-800 text-white font-mono font-bold text-[11px] border border-slate-700">
                        {r.room_number || 'N/A'}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-bold text-white group-hover:text-amber-400 transition-colors">
                      {r.guest_name}
                      {r.additional_guests && (
                        <div className="text-[10px] text-slate-500 font-normal">Add'l: {r.additional_guests}</div>
                      )}
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-300">{r.confirmation_number || 'N/A'}</td>
                    <td className="py-3 px-4 font-mono text-slate-300">{r.check_in_date || 'N/A'}</td>
                    <td className="py-3 px-4 font-mono font-bold text-white">{r.number_of_nights ?? 'N/A'}</td>
                    <td className="py-3 px-4 font-mono text-slate-300">{r.calculated_departure_date || 'N/A'}</td>
                    <td className="py-3 px-4">
                      <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300">
                        {r.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-slate-400">{r.actual_departed_time || '-'}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          if (r.guest_identity_id) setSelectedGuestId(r.guest_identity_id);
                        }}
                        className="p-1 rounded hover:bg-slate-700 text-slate-400 hover:text-white"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={10} className="py-8 text-center text-slate-500 text-xs">
                    No records matched criteria.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <GuestDetailModal identityId={selectedGuestId} onClose={() => setSelectedGuestId(null)} />
    </div>
  );
};
