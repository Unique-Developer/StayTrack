import {
  DashboardSummary,
  ReportPreviewFile,
  ReportItem,
  GuestMonitoringResponse,
  GuestDetail,
  ReviewQueueData,
  SystemSettings,
  AuditLogItem,
  PreviewRecord
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL
  ? `${String(import.meta.env.VITE_API_BASE_URL).replace(/\/$/, '')}/api/v1`
  : '/api/v1';

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = 'An error occurred';
    try {
      const err = await res.json();
      errorMsg = err.detail || err.message || errorMsg;
    } catch {
      errorMsg = res.statusText || errorMsg;
    }
    throw new Error(errorMsg);
  }
  return res.json();
}

export const api = {
  // Dashboard
  async getDashboardSummary(): Promise<DashboardSummary> {
    const res = await fetch(`${API_BASE}/dashboard/summary`);
    return handleResponse<DashboardSummary>(res);
  },

  // Reports Upload & Workflow
  async previewReports(files: File[]): Promise<ReportPreviewFile[]> {
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    const res = await fetch(`${API_BASE}/reports/preview`, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<ReportPreviewFile[]>(res);
  },

  async commitReports(payload: {
    files: Array<{
      temp_file_id: string;
      report_date: string;
      replace_existing_id?: number;
      records: PreviewRecord[];
    }>;
  }): Promise<{ success: boolean; message: string; imported_report_ids: number[] }> {
    const res = await fetch(`${API_BASE}/reports/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return handleResponse(res);
  },

  async getReports(): Promise<ReportItem[]> {
    const res = await fetch(`${API_BASE}/reports`);
    return handleResponse<ReportItem[]>(res);
  },

  getDownloadUrl(reportId: number): string {
    return `${API_BASE}/reports/${reportId}/download`;
  },

  async deleteReport(reportId: number): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/reports/${reportId}`, {
      method: 'DELETE',
    });
    return handleResponse(res);
  },

  // Guest Monitoring
  async getGuestMonitoring(params: {
    mode?: string;
    search?: string;
    verification_status?: string;
    min_appearances?: number;
    min_duration?: number;
    room?: string;
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: string;
  }): Promise<GuestMonitoringResponse> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        searchParams.append(k, String(v));
      }
    });
    const res = await fetch(`${API_BASE}/guests/monitoring?${searchParams.toString()}`);
    return handleResponse<GuestMonitoringResponse>(res);
  },

  getGuestExportUrl(params: { mode?: string; verification_status?: string; search?: string }): string {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) searchParams.append(k, v);
    });
    return `${API_BASE}/guests/export?${searchParams.toString()}`;
  },

  getGuestExportPdfUrl(params?: { search?: string; min_nights?: number; property_id?: number }): string {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          searchParams.append(k, String(v));
        }
      });
    }
    return `${API_BASE}/guests/export-pdf?${searchParams.toString()}`;
  },

  async getGuestDetail(identityId: number): Promise<GuestDetail> {
    const res = await fetch(`${API_BASE}/guests/${identityId}`);
    return handleResponse<GuestDetail>(res);
  },

  // All Records
  async getAllRecords(params: {
    search?: string;
    report_date?: string;
    room?: string;
    page?: number;
    page_size?: number;
    sort_by?: string;
    sort_order?: string;
  }): Promise<{ total: number; page: number; page_size: number; items: any[] }> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        searchParams.append(k, String(v));
      }
    });
    const res = await fetch(`${API_BASE}/records?${searchParams.toString()}`);
    return handleResponse(res);
  },

  getAllRecordsExportUrl(params: { search?: string; report_date?: string; room?: string }): string {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) searchParams.append(k, v);
    });
    return `${API_BASE}/records/export?${searchParams.toString()}`;
  },

  // Review Queue
  async getReviewQueue(): Promise<ReviewQueueData> {
    const res = await fetch(`${API_BASE}/review/queue`);
    return handleResponse<ReviewQueueData>(res);
  },

  async confirmIdentityMatch(matchId: number): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/review/matches/${matchId}/confirm`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async rejectIdentityMatch(matchId: number): Promise<{ success: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/review/matches/${matchId}/reject`, {
      method: 'POST',
    });
    return handleResponse(res);
  },

  async verifyAssessment(
    assessmentId: number,
    action: 'verify' | 'reject',
    notes?: string
  ): Promise<{ success: boolean; status: string }> {
    const res = await fetch(`${API_BASE}/review/assessments/${assessmentId}/verify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action, notes }),
    });
    return handleResponse(res);
  },

  // Settings
  async getSettings(): Promise<SystemSettings> {
    const res = await fetch(`${API_BASE}/settings`);
    return handleResponse<SystemSettings>(res);
  },

  async updateSettings(data: Partial<SystemSettings>): Promise<SystemSettings> {
    const res = await fetch(`${API_BASE}/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<SystemSettings>(res);
  },

  // Audit Logs
  async getAuditLogs(params: { action?: string; page?: number; page_size?: number }): Promise<{
    total: number;
    page: number;
    page_size: number;
    items: AuditLogItem[];
  }> {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') {
        searchParams.append(k, String(v));
      }
    });
    const res = await fetch(`${API_BASE}/audit/logs?${searchParams.toString()}`);
    return handleResponse(res);
  },
};
