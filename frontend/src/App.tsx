import React, { useState, useEffect } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LoginPage } from './pages/LoginPage';
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
import { Loader2 } from 'lucide-react';

function MainApp() {
  const { user, isAuthenticated, isLoading, logout } = useAuth();
  const [currentTab, setCurrentTab] = useState<string>('dashboard');
  const [summary, setSummary] = useState<DashboardSummary | undefined>(undefined);
  const [reviewCount, setReviewCount] = useState<number>(0);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadDashboardData = async () => {
    if (!isAuthenticated) return;
    setIsRefreshing(true);
    setLoadError(null);
    try {
      const sum = await api.getDashboardSummary();
      setSummary(sum);

      const reviewData = await api.getReviewQueue();
      setReviewCount((reviewData.pending_matches_count || 0) + (reviewData.uncertain_assessments_count || 0));
    } catch (err: any) {
      console.error('Failed to load dashboard data:', err);
      setLoadError(err.message || 'Unable to connect to backend server');
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (isAuthenticated) {
      loadDashboardData();
    }
  }, [isAuthenticated]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-6 text-slate-100">
        <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-500 to-amber-600 flex items-center justify-center text-slate-950 font-black text-2xl shadow-xl shadow-amber-500/25 mb-4 animate-pulse">
          S6
        </div>
        <div className="flex items-center gap-2.5 text-sm font-medium text-slate-400">
          <Loader2 className="w-4 h-4 animate-spin text-amber-400" />
          <span>Verifying StayTrack session...</span>
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <LoginPage />;
  }

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
        user={user}
        onLogout={logout}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <Header
          summary={summary}
          onUploadClick={() => setCurrentTab('upload')}
          onRefresh={loadDashboardData}
          isRefreshing={isRefreshing}
          user={user}
          onLogout={logout}
        />

        <main className="flex-1 p-6 md:p-8 overflow-y-auto">
          {currentTab === 'dashboard' && summary && (
            <DashboardPage summary={summary} onNavigate={setCurrentTab} />
          )}
          {currentTab === 'dashboard' && !summary && !loadError && (
            <div className="py-20 text-center text-slate-500 animate-pulse">
              Loading StayTrack motel metrics...
            </div>
          )}
          {currentTab === 'dashboard' && !summary && loadError && (
            <div className="py-16 text-center max-w-lg mx-auto bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-xl mt-6">
              <div className="w-12 h-12 bg-amber-500/10 text-amber-400 rounded-full flex items-center justify-center mx-auto mb-4 border border-amber-500/20 text-xl font-bold">
                !
              </div>
              <h3 className="text-lg font-semibold text-slate-100 mb-2">Connecting to Backend API</h3>
              <p className="text-sm text-slate-400 mb-6 leading-relaxed">
                Could not connect to the StayTrack backend. On Render's Free tier, the service takes about 45–60 seconds to spin up from sleep, or may still be deploying.
              </p>
              <div className="flex justify-center gap-3">
                <button
                  onClick={loadDashboardData}
                  disabled={isRefreshing}
                  className="px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium rounded-lg transition-colors shadow-lg shadow-blue-900/30 disabled:opacity-50 cursor-pointer"
                >
                  {isRefreshing ? 'Retrying...' : 'Retry Connection'}
                </button>
                <a
                  href="https://staytrack-o6ah.onrender.com/health"
                  target="_blank"
                  rel="noreferrer"
                  className="px-5 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium rounded-lg transition-colors border border-slate-700"
                >
                  Check Backend Status ↗
                </a>
              </div>
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

export function App() {
  return (
    <AuthProvider>
      <MainApp />
    </AuthProvider>
  );
}

export default App;
