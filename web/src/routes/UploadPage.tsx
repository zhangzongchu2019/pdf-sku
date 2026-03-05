import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUploadStore } from "../stores/uploadStore";
import { useJobStore } from "../stores/jobStore";
import { useNotificationStore } from "../stores/notificationStore";
import { formatBytes } from "../utils/format";

const MAX_SIZE = 16 * 1024 * 1024 * 1024; // 16GB

export default function UploadPage() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const { uploads, addFile, startUpload, removeUpload, clearCompleted, merchantId, category, setMerchantId, setCategory } = useUploadStore();
  const createJob = useJobStore((s) => s.createJob);
  const notify = useNotificationStore((s) => s.add);
  const [dragActive, setDragActive] = useState(false);

  const handleUploadAndCreate = useCallback(async (uploadId: string) => {
    try {
      const fileId = await startUpload(uploadId);
      const job = await createJob(fileId, merchantId, category || undefined);
      notify({
        type: "success",
        message: job.is_duplicate
          ? `该文件已存在，跳转到已有任务: ${job.job_id.slice(0, 8)}...`
          : `Job 创建成功: ${job.job_id.slice(0, 8)}...`,
      });
      // 所有上传都完成后跳转：单文件跳详情，多文件跳列表
      const stillActive = useUploadStore.getState().uploads.filter(
        (u) => u.id !== uploadId && (u.status === "pending" || u.status === "uploading")
      );
      if (stillActive.length === 0) {
        const allUploads = useUploadStore.getState().uploads;
        navigate(allUploads.length === 1 ? `/jobs/${job.job_id}` : "/jobs");
      }
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  }, [merchantId, category, startUpload, createJob, notify, navigate]);

  const handleFiles = useCallback((files: FileList | File[]) => {
    if (!merchantId.trim()) {
      notify({ type: "error", message: "请先输入商户 ID" });
      return;
    }
    for (const file of Array.from(files)) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        notify({ type: "error", message: `${file.name} 不是 PDF 文件` });
        continue;
      }
      if (file.size > MAX_SIZE) {
        notify({ type: "error", message: `${file.name} 超过 16GB 限制` });
        continue;
      }
      const uploadId = addFile(file);
      handleUploadAndCreate(uploadId);
    }
  }, [addFile, notify, merchantId, handleUploadAndCreate]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    handleFiles(e.dataTransfer.files);
  }, [handleFiles]);

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
        onClick={() => fileRef.current?.click()}
      >
        <input ref={fileRef} type="file" accept=".pdf" multiple hidden
               onChange={(e) => e.target.files && handleFiles(e.target.files)} />
        <div className="dropzone-content">
          <span className="dropzone-icon">📁</span>
          <p>拖拽 PDF 文件到此处，或点击选择</p>
          <p className="dropzone-hint">支持批量上传，单文件最大 16GB</p>
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
                <span className="upload-status">
                  {u.status === "uploading" ? `${u.progress.percentage}%` : u.status}
                </span>
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
