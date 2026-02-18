import { BrowserRouter, Routes, Route } from "react-router-dom";
import { lazy, Suspense } from "react";
import Layout from "./components/common/Layout";
import { ErrorBoundary } from "./components/common/ErrorBoundary";
import { PageSkeleton } from "./components/common/PageSkeleton";
import { RequireAuth } from "./components/common/RequireAuth";

/* ---- lazy pages ---- */
const LoginPage          = lazy(() => import("./routes/LoginPage"));
const RegisterPage       = lazy(() => import("./routes/RegisterPage"));
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
const UserManagePage     = lazy(() => import("./routes/UserManagePage"));
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

function Protected({ children, roles }: { children: React.ReactNode; roles?: string[] }) {
  return (
    <RequireAuth roles={roles}>
      <LazyPage>{children}</LazyPage>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 公开页: 登录 / 注册 (不带 Layout) */}
        <Route path="/login" element={<LazyPage><LoginPage /></LazyPage>} />
        <Route path="/register" element={<LazyPage><RegisterPage /></LazyPage>} />

        {/* 所有业务页面 — 都要求登录 */}
        <Route path="/*" element={
          <Layout>
            <Routes>
              {/* Dashboard — 所有角色 */}
              <Route path="/" element={<Protected><DashboardPage /></Protected>} />
              <Route path="/dashboard" element={<Protected><DashboardPage /></Protected>} />

              {/* Upload — 仅 uploader / admin */}
              <Route path="/upload" element={<Protected roles={["uploader", "admin"]}><UploadPage /></Protected>} />

              {/* Jobs — 所有已登录 */}
              <Route path="/jobs" element={<Protected><JobListPage /></Protected>} />
              <Route path="/jobs/:jobId" element={<Protected><JobDetailPage /></Protected>} />

              {/* Tasks — 所有已登录 */}
              <Route path="/tasks" element={<Protected><TaskListPage /></Protected>} />

              {/* Annotation — 仅 annotator / admin */}
              <Route path="/annotate/:taskId" element={<Protected roles={["annotator", "admin"]}><AnnotationPage /></Protected>} />
              <Route path="/annotate/my-stats" element={<Protected roles={["annotator", "admin"]}><MyStatsPage /></Protected>} />
              <Route path="/annotate/history" element={<Protected roles={["annotator", "admin"]}><HistoryPage /></Protected>} />

              {/* User Management — admin */}
              <Route path="/admin/users" element={<Protected roles={["admin"]}><UserManagePage /></Protected>} />

              {/* Config — admin */}
              <Route path="/config" element={<Protected roles={["admin"]}><ConfigPage /></Protected>} />
              <Route path="/config/:profileId" element={<Protected roles={["admin"]}><ConfigEditPage /></Protected>} />

              {/* Merchants */}
              <Route path="/merchants/:merchantId" element={<Protected><MerchantJobsPage /></Protected>} />

              {/* Annotators (Ops) — admin */}
              <Route path="/annotators" element={<Protected roles={["admin"]}><AnnotatorListPage /></Protected>} />
              <Route path="/annotators/:annotatorId" element={<Protected roles={["admin"]}><AnnotatorDetailPage /></Protected>} />

              {/* Evaluation — admin */}
              <Route path="/eval" element={<Protected roles={["admin"]}><EvalListPage /></Protected>} />
              <Route path="/eval/:reportId" element={<Protected roles={["admin"]}><EvalDetailPage /></Protected>} />

              {/* Custom Attr Upgrades (Ops) — admin */}
              <Route path="/ops/custom-attr-upgrades" element={<Protected roles={["admin"]}><CustomAttrUpgradesPage /></Protected>} />

              {/* Notifications — 所有 */}
              <Route path="/notifications" element={<Protected><NotificationPage /></Protected>} />

              {/* Settings — 所有 */}
              <Route path="/settings" element={<Protected><SettingsPage /></Protected>} />
            </Routes>
          </Layout>
        } />
      </Routes>
    </BrowserRouter>
  );
}
