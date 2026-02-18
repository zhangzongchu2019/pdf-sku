import { BrowserRouter, Routes, Route } from "react-router-dom";
import { lazy, Suspense } from "react";
import Layout from "./components/common/Layout";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { PageSkeleton } from "./components/common/PageSkeleton";

/* ---- lazy pages ---- */
const DashboardPage      = lazy(() => import("./routes/DashboardPage"));
const UploadPage         = lazy(() => import("./routes/UploadPage"));
const JobListPage        = lazy(() => import("./routes/JobListPage"));
const JobDetailPage      = lazy(() => import("./routes/JobDetailPage"));
const TaskListPage       = lazy(() => import("./routes/TaskListPage"));
const AnnotationPage     = lazy(() => import("./routes/AnnotationPage"));
const ConfigPage         = lazy(() => import("./routes/ConfigPage"));
const ConfigEditPage     = lazy(() => import("./routes/ConfigEditPage"));
const MyStatsPage        = lazy(() => import("./routes/MyStatsPage"));
const HistoryPage        = lazy(() => import("./routes/HistoryPage"));
const MerchantJobsPage   = lazy(() => import("./routes/MerchantJobsPage"));
const AnnotatorListPage  = lazy(() => import("./routes/AnnotatorListPage"));
const AnnotatorDetailPage = lazy(() => import("./routes/AnnotatorDetailPage"));
const EvalListPage       = lazy(() => import("./routes/EvalListPage"));
const EvalDetailPage     = lazy(() => import("./routes/EvalDetailPage"));
const CustomAttrUpgradesPage = lazy(() => import("./routes/CustomAttrUpgradesPage"));
const NotificationPage   = lazy(() => import("./routes/NotificationPage"));
const SettingsPage       = lazy(() => import("./routes/SettingsPage"));

function LazyPage({ children }: { children: React.ReactNode }) {
  return (
    <ErrorBoundary>
      <Suspense fallback={<PageSkeleton />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          {/* Dashboard */}
          <Route path="/" element={<LazyPage><DashboardPage /></LazyPage>} />
          <Route path="/dashboard" element={<LazyPage><DashboardPage /></LazyPage>} />

          {/* Upload */}
          <Route path="/upload" element={<LazyPage><UploadPage /></LazyPage>} />

          {/* Jobs */}
          <Route path="/jobs" element={<LazyPage><JobListPage /></LazyPage>} />
          <Route path="/jobs/:jobId" element={<LazyPage><JobDetailPage /></LazyPage>} />

          {/* Tasks */}
          <Route path="/tasks" element={<LazyPage><TaskListPage /></LazyPage>} />

          {/* Annotation */}
          <Route path="/annotate/:taskId" element={<LazyPage><AnnotationPage /></LazyPage>} />
          <Route path="/annotate/my-stats" element={<LazyPage><MyStatsPage /></LazyPage>} />
          <Route path="/annotate/history" element={<LazyPage><HistoryPage /></LazyPage>} />

          {/* Config */}
          <Route path="/config" element={<LazyPage><ConfigPage /></LazyPage>} />
          <Route path="/config/:profileId" element={<LazyPage><ConfigEditPage /></LazyPage>} />

          {/* Merchants */}
          <Route path="/merchants/:merchantId" element={<LazyPage><MerchantJobsPage /></LazyPage>} />

          {/* Annotators (Ops) */}
          <Route path="/annotators" element={<LazyPage><AnnotatorListPage /></LazyPage>} />
          <Route path="/annotators/:annotatorId" element={<LazyPage><AnnotatorDetailPage /></LazyPage>} />

          {/* Evaluation */}
          <Route path="/eval" element={<LazyPage><EvalListPage /></LazyPage>} />
          <Route path="/eval/:reportId" element={<LazyPage><EvalDetailPage /></LazyPage>} />

          {/* Custom Attr Upgrades (Ops) */}
          <Route path="/ops/custom-attr-upgrades" element={<LazyPage><CustomAttrUpgradesPage /></LazyPage>} />

          {/* Notifications */}
          <Route path="/notifications" element={<LazyPage><NotificationPage /></LazyPage>} />

          {/* Settings */}
          <Route path="/settings" element={<LazyPage><SettingsPage /></LazyPage>} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
