import React, { useState, useRef } from 'react';
import {
  UploadCloud,
  FileText,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Trash2,
  Calendar,
  Building2,
  ShieldAlert,
  ArrowRight
} from 'lucide-react';
import { api } from '../services/api';
import { ReportPreviewFile, PreviewRecord } from '../types';

interface UploadPageProps {
  onImportComplete: () => void;
}

export const UploadPage: React.FC<UploadPageProps> = ({ onImportComplete }) => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<ReportPreviewFile[]>([]);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const validPdfs: File[] = [];
    for (let i = 0; i < files.length; i++) {
      if (files[i].name.toLowerCase().endsWith('.pdf')) {
        validPdfs.push(files[i]);
      }
    }

    if (validPdfs.length === 0) {
      setErrorMessage('Please select valid PDF files (.pdf)');
      return;
    }

    setSelectedFiles(validPdfs);
    setErrorMessage(null);
    setSuccessMessage(null);
    setLoadingPreview(true);

    try {
      const results = await api.previewReports(validPdfs);
      setPreviews(results);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to parse reports');
    } finally {
      setLoadingPreview(false);
    }
  };

  const handleDateChange = (previewIndex: number, newDate: string) => {
    const updated = [...previews];
    updated[previewIndex].report_date = newDate;
    setPreviews(updated);
  };

  const handleRecordChange = (previewIndex: number, recordIndex: number, field: keyof PreviewRecord, val: any) => {
    const updated = [...previews];
    (updated[previewIndex].records[recordIndex] as any)[field] = val;
    setPreviews(updated);
  };

  const handleRemovePreview = (index: number) => {
    const updated = [...previews];
    updated.splice(index, 1);
    setPreviews(updated);
  };

  const handleConfirmCommit = async () => {
    if (previews.length === 0) return;
    setCommitting(true);
    setErrorMessage(null);

    try {
      const payload = {
        files: previews.map((p) => ({
          temp_file_id: p.temp_file_id,
          report_date: p.report_date || new Date().toISOString().split('T')[0],
          replace_existing_id: p.existing_report_for_date_id,
          records: p.records,
        })),
      };

      const res = await api.commitReports(payload);
      setSuccessMessage(res.message);
      setPreviews([]);
      setSelectedFiles([]);
      onImportComplete();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to commit imported reports');
    } finally {
      setCommitting(false);
    }
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight flex items-center gap-2.5">
          <UploadCloud className="w-6 h-6 text-amber-400" /> Upload Daily Reports
        </h1>
        <p className="text-xs text-slate-400 mt-1">
          Upload daily "Departures List" PDFs to extract guest stay records, detect continuous stays, and update the
          rolling window analytics.
        </p>
      </div>

      {/* Alert Banners */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {successMessage && (
        <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-sm flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <span>{successMessage}</span>
          </div>
          <button
            onClick={onImportComplete}
            className="text-xs font-bold text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
          >
            <span>View Monitoring</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Drag & Drop Upload Zone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          handleFileChange(e.dataTransfer.files);
        }}
        className="cursor-pointer border-2 border-dashed border-slate-700 hover:border-amber-500/80 rounded-2xl p-8 bg-slate-900/60 hover:bg-slate-900 transition-all text-center group"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          multiple
          className="hidden"
          onChange={(e) => handleFileChange(e.target.files)}
        />
        <div className="w-14 h-14 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-400 flex items-center justify-center mx-auto group-hover:scale-110 transition-transform shadow-lg shadow-amber-500/10">
          <UploadCloud className="w-7 h-7" />
        </div>
        <div className="mt-4">
          <span className="text-base font-bold text-white group-hover:text-amber-400 transition-colors">
            Click to upload
          </span>{' '}
          <span className="text-slate-400 text-sm">or drag and drop departure reports</span>
        </div>
        <p className="text-xs text-slate-500 mt-1">Supports Studio 6 Departure PDFs (Single or Multiple files)</p>
      </div>

      {/* Loading Indicator */}
      {loadingPreview && (
        <div className="py-12 text-center text-slate-400 space-y-3">
          <RefreshCw className="w-8 h-8 text-amber-400 animate-spin mx-auto" />
          <div className="text-sm font-semibold text-slate-300">
            Extracting text, table rows, and validating dates...
          </div>
          <div className="text-xs text-slate-500">Checking duplicate file hashes and historical coverage</div>
        </div>
      )}

      {/* Staging & Review Table (Before Commit) */}
      {previews.length > 0 && !loadingPreview && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
              <FileText className="w-5 h-5 text-amber-400" /> Review Staged Reports ({previews.length})
            </h2>
            <button
              onClick={handleConfirmCommit}
              disabled={committing}
              className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-sm shadow-lg shadow-amber-500/25 transition-all active:scale-[0.98] disabled:opacity-50"
            >
              {committing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  <span>Committing & Recalculating...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Confirm Import ({previews.reduce((a, b) => a + b.records.length, 0)} Records)</span>
                </>
              )}
            </button>
          </div>

          {previews.map((preview, pIdx) => (
            <div key={preview.temp_file_id} className="rounded-xl bg-slate-900 border border-slate-800 overflow-hidden">
              {/* Report Header Metadata Banner */}
              <div className="p-4 bg-slate-950/80 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-slate-800 border border-slate-700 flex items-center justify-center font-bold text-amber-400 text-xs">
                    PDF
                  </div>
                  <div>
                    <div className="text-sm font-bold text-white">{preview.original_filename}</div>
                    <div className="text-xs text-slate-400 flex items-center gap-3 mt-0.5">
                      <span>{preview.property_name || 'STUDIO 6 - STAFFORD, VA'}</span>
                      <span>•</span>
                      <span>Property #{preview.property_code || '3756'}</span>
                      <span>•</span>
                      <span>{preview.total_rows} row(s) extracted</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-4">
                  {/* Reporting Date with Manual Override */}
                  <div className="flex items-center gap-2 bg-slate-800/80 border border-slate-700 px-3 py-1.5 rounded-lg">
                    <Calendar className="w-3.5 h-3.5 text-amber-400" />
                    <span className="text-xs text-slate-400">Report Date:</span>
                    <input
                      type="date"
                      value={preview.report_date || ''}
                      onChange={(e) => handleDateChange(pIdx, e.target.value)}
                      className="bg-slate-900 text-white font-mono text-xs px-2 py-0.5 rounded border border-slate-700 focus:outline-none focus:border-amber-400"
                    />
                  </div>

                  <button
                    onClick={() => handleRemovePreview(pIdx)}
                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-500 hover:text-rose-400 transition-colors"
                    title="Remove file"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Duplicate & Existing Date Warnings */}
              {preview.is_duplicate && (
                <div className="p-3 bg-amber-500/10 border-b border-amber-500/30 text-amber-300 text-xs flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
                  <span>
                    <strong>Duplicate File Notice:</strong> An identical PDF has already been imported (Report ID #
                    {preview.duplicate_report_id}). Re-importing will replace or refresh the records.
                  </span>
                </div>
              )}

              {preview.existing_report_for_date_id && !preview.is_duplicate && (
                <div className="p-3 bg-blue-500/10 border-b border-blue-500/30 text-blue-300 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-blue-400 shrink-0" />
                  <span>
                    <strong>Existing Date Coverage:</strong> A report for date {preview.report_date} already exists.
                    Confirming will replace the previous report and retain an audit trail.
                  </span>
                </div>
              )}

              {/* Editable Records Preview Table */}
              <div className="max-h-72 overflow-y-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-950/60 text-slate-400 uppercase tracking-wider sticky top-0 border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">Conf No</th>
                      <th className="py-2.5 px-3">Room</th>
                      <th className="py-2.5 px-3">Guest Name</th>
                      <th className="py-2.5 px-3">Check-In</th>
                      <th className="py-2.5 px-3">Nights</th>
                      <th className="py-2.5 px-3">Calc Departure</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3">Quality</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 bg-slate-900/40 text-slate-300">
                    {preview.records.map((rec, rIdx) => (
                      <tr key={rIdx} className="hover:bg-slate-800/30 transition-colors">
                        <td className="py-2 px-3 font-mono">
                          <input
                            type="text"
                            value={rec.confirmation_number || ''}
                            onChange={(e) => handleRecordChange(pIdx, rIdx, 'confirmation_number', e.target.value)}
                            className="bg-transparent border border-transparent hover:border-slate-700 focus:border-amber-400 rounded px-1.5 py-0.5 text-amber-300 font-mono w-28 focus:outline-none"
                          />
                        </td>
                        <td className="py-2 px-3">
                          <input
                            type="text"
                            value={rec.room_number || ''}
                            onChange={(e) => handleRecordChange(pIdx, rIdx, 'room_number', e.target.value)}
                            className="bg-transparent border border-transparent hover:border-slate-700 focus:border-amber-400 rounded px-1.5 py-0.5 font-bold text-white w-16 focus:outline-none"
                          />
                        </td>
                        <td className="py-2 px-3">
                          <input
                            type="text"
                            value={rec.normalized_name}
                            onChange={(e) => handleRecordChange(pIdx, rIdx, 'normalized_name', e.target.value)}
                            className="bg-transparent border border-transparent hover:border-slate-700 focus:border-amber-400 rounded px-1.5 py-0.5 font-semibold text-slate-100 w-44 focus:outline-none"
                          />
                        </td>
                        <td className="py-2 px-3 font-mono text-slate-300">{rec.check_in_date || 'N/A'}</td>
                        <td className="py-2 px-3 font-mono font-bold text-white">{rec.number_of_nights ?? 'N/A'}</td>
                        <td className="py-2 px-3 font-mono text-slate-300">{rec.calculated_departure_date || 'N/A'}</td>
                        <td className="py-2 px-3">
                          <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-800 text-slate-300 font-medium">
                            {rec.status}
                          </span>
                        </td>
                        <td className="py-2 px-3">
                          {rec.confidence_score >= 0.85 ? (
                            <span className="text-emerald-400 text-[11px] font-bold">100%</span>
                          ) : (
                            <span
                              className="text-amber-400 text-[11px] font-bold cursor-help"
                              title={rec.validation_flags.join(', ')}
                            >
                              {(rec.confidence_score * 100).toFixed(0)}% Flagged
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
