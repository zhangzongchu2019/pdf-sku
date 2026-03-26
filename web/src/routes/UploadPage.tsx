import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUploadStore } from "../stores/uploadStore";
import { useJobStore } from "../stores/jobStore";
import { useNotificationStore } from "../stores/notificationStore";
import { formatBytes, formatStatusLabel } from "../utils/format";

const MAX_SIZE = 100 * 1024 * 1024; // 100MB

export default function UploadPage() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const {
    uploads,
    addFile,
    startUpload,
    setStatus,
    setError,
    removeUpload,
    clearCompleted,
  } = useUploadStore();
  const createJob = useJobStore((s) => s.createJob);
  const notify = useNotificationStore((s) => s.add);

  const [merchantId, setMerchantId] = useState("");
  const [category, setCategory] = useState("");
  const [dragActive, setDragActive] = useState(false);

  const uploadAndCreateJob = useCallback(async (
    uploadId: string,
    merchantIdValue: string,
    categoryValue?: string,
    navigateOnSuccess = false,
  ) => {
    try {
      const fileId = await startUpload(uploadId);
      const job = await createJob(fileId, merchantIdValue, categoryValue);
      setStatus(uploadId, "completed");
      notify({ type: "success", message: `任务创建成功: ${job.job_id.slice(0, 8)}...` });
      if (navigateOnSuccess) {
        navigate(`/jobs/${job.job_id}`);
      }
    } catch (e: any) {
      const message = e?.message || "上传失败";
      setError(uploadId, message);
      notify({ type: "error", message });
    }
  }, [startUpload, createJob, setStatus, setError, notify, navigate]);

  const handleFiles = useCallback((files: FileList | File[]) => {
    const merchantIdValue = merchantId.trim();
    if (!merchantIdValue) {
      notify({ type: "error", message: "请先填写商户 ID，再拖拽或选择文件" });
      return;
    }

    const categoryValue = category.trim() || undefined;
    const validFiles: File[] = [];

    for (const file of Array.from(files)) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        notify({ type: "error", message: `${file.name} 不是 PDF 文件` });
        continue;
      }
      if (file.size > MAX_SIZE) {
        notify({ type: "error", message: `${file.name} 超过 100MB 限制` });
        continue;
      }
      validFiles.push(file);
    }

    const navigateOnSuccess = validFiles.length === 1;
    for (const file of validFiles) {
      const uploadId = addFile(file);
      void uploadAndCreateJob(uploadId, merchantIdValue, categoryValue, navigateOnSuccess);
    }
  }, [merchantId, category, addFile, notify, uploadAndCreateJob]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

  const handlePickFiles = useCallback(() => {
    if (!merchantId.trim()) {
      notify({ type: "error", message: "请先填写商户 ID，再选择文件" });
      return;
    }
    fileRef.current?.click();
  }, [merchantId, notify]);

  const renderUploadStatus = useCallback((status: typeof uploads[number]["status"], progress: number) => {
    if (status === "uploading") return `上传中 ${progress}%`;
    return formatStatusLabel(status);
  }, []);

  return (
    <div className="page upload-page">
      <h2>上传 PDF 目录</h2>

      <div className="form-row">
        <label>商户 ID *</label>
        <input value={merchantId} onChange={(e) => setMerchantId(e.target.value)}
               placeholder="例: merchant_001" className="input" />
      </div>
      <div className="form-row">
        <label>品类 (可选)</label>
        <input value={category} onChange={(e) => setCategory(e.target.value)}
               placeholder="例: electronics" className="input" />
      </div>

      <div
        className={`dropzone ${dragActive ? "dropzone-active" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={handlePickFiles}
      >
        <input ref={fileRef} type="file" accept=".pdf" multiple hidden
               onChange={(e) => {
                 if (e.target.files) handleFiles(e.target.files);
                 e.target.value = "";
               }} />
        <div className="dropzone-content">
          <span className="dropzone-icon">📁</span>
          <p>拖拽 PDF 文件到此处，或点击选择后立即上传</p>
          <p className="dropzone-hint">请先填写商户 ID。支持批量上传，单文件最大 100MB</p>
        </div>
      </div>

      {uploads.length > 0 && (
        <div className="upload-list">
          <div className="upload-list-header">
            <h3>上传队列 ({uploads.length})</h3>
            <button className="btn btn-text" onClick={clearCompleted}>清除已完成</button>
          </div>
          {uploads.map((u) => (
            <div key={u.id} className="upload-item">
              <div className="upload-info">
                <span className="upload-name">{u.file.name}</span>
                <span className="upload-size">{formatBytes(u.file.size)}</span>
              </div>
              <div className="upload-progress-bar">
                <div className="upload-progress-fill"
                     style={{ width: `${u.progress.percentage}%` }} />
              </div>
              <div className="upload-actions">
                <span className="upload-status">{renderUploadStatus(u.status, u.progress.percentage)}</span>
                {u.status === "error" && <span className="error-text">{u.error}</span>}
                <button className="btn btn-text btn-sm" onClick={() => removeUpload(u.id)}>✕</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
