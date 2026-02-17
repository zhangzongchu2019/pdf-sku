import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/common/Layout";
import DashboardPage from "./routes/DashboardPage";
import UploadPage from "./routes/UploadPage";
import JobListPage from "./routes/JobListPage";
import JobDetailPage from "./routes/JobDetailPage";
import TaskListPage from "./routes/TaskListPage";
import AnnotationPage from "./routes/AnnotationPage";
import ConfigPage from "./routes/ConfigPage";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/jobs" element={<JobListPage />} />
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
          <Route path="/tasks" element={<TaskListPage />} />
          <Route path="/annotate/:taskId" element={<AnnotationPage />} />
          <Route path="/config" element={<ConfigPage />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}
