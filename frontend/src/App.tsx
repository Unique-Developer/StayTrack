import React, { useState, useEffect } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { DashboardPage } from './pages/DashboardPage';
import { UploadPage } from './pages/UploadPage';
import { GuestMonitoringPage } from './pages/GuestMonitoringPage';
import { AllRecordsPage } from './pages/AllRecordsPage';
import { ReportHistoryPage } from './pages/ReportHistoryPage';
import { ReviewQueuePage } from './pages/ReviewQueuePage';
import { SettingsPage } from './pages/SettingsPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { api } from './services/api';
import { DashboardSummary } from './types';

export function App() {
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [summary, setSummary] = useState<DashboardSummary | undefined>(undefined);
  const [reviewCount, setReviewCount] = useState<number>(0);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const loadDashboardData = async () => {
    setIsRefreshing(true);
    try {
      const sum = await api.getDashboardSummary();
      setSummary(sum);

      const reviewData = await api.getReviewQueue();
      setReviewCount((reviewData.pending_matches_count || 0) + (reviewData.uncertain_assessments_count || 0));
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadDashboardData();
  }, []);

  const handleUploadComplete = () => {
    loadDashboardData();
    setCurrentTab('monitoring');
  };

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100 font-sans antialiased">
      {/* Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        reviewCount={reviewCount}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          summary={summary}
          onUploadClick={() => setCurrentTab('upload')}
          onRefresh={loadDashboardData}
          isRefreshing={isRefreshing}
        />

        <main className="flex-1 p-6 md:p-8 overflow-y-auto">
          {currentTab === 'dashboard' && summary && (
            <DashboardPage summary={summary} onNavigate={setCurrentTab} />
          )}
          {currentTab === 'dashboard' && !summary && (
            <div className="py-20 text-center text-slate-500 animate-pulse">
              Loading StayTrack motel metrics...
            </div>
          )}
          {currentTab === 'upload' && (
            <UploadPage onImportComplete={handleUploadComplete} />
          )}
          {currentTab === 'monitoring' && <GuestMonitoringPage />}
          {currentTab === 'records' && <AllRecordsPage />}
          {currentTab === 'history' && <ReportHistoryPage />}
          {currentTab === 'review' && <ReviewQueuePage />}
          {currentTab === 'settings' && <SettingsPage />}
          {currentTab === 'audit' && <AuditLogPage />}
        </main>
      </div>
    </div>
  );
}

export default App;
