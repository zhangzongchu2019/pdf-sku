import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useUploadStore } from "../stores/uploadStore";
import { useJobStore } from "../stores/jobStore";
import { useNotificationStore } from "../stores/notificationStore";
import { useAuthStore } from "../stores/authStore";
import { formatBytes } from "../utils/format";
import api from "../api/client";

const MAX_SIZE = 1024 * 1024 * 1024; // 1GB

export default function UploadPage() {
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);
  const { uploads, addFile, startUpload, removeUpload, clearCompleted } = useUploadStore();
  const createJob = useJobStore((s) => s.createJob);
  const notify = useNotificationStore((s) => s.add);
  const authMerchantId = useAuthStore((s) => s.merchantId);

  const [merchantId, setMerchantId] = useState(authMerchantId || "");
  const [category, setCategory] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [merchantList, setMerchantList] = useState<string[]>([]);
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    api.get<{ data: string[] }>("/merchants").then((res) => {
      setMerchantList(res.data || []);
      // 优先用当前用户的 merchantId，其次用最近使用的
      if (!authMerchantId && res.data?.length) setMerchantId(res.data[0]);
    }).catch(() => {});
  }, [authMerchantId]);

  const doUploadAndCreate = useCallback(async (uploadId: string) => {
    if (!merchantId.trim()) {
      notify({ type: "error", message: "请输入商户 ID" });
      return;
    }
    try {
      const fileId = await startUpload(uploadId);
      const job = await createJob(fileId, merchantId, category || undefined);
      notify({ type: "success", message: `Job 创建成功: ${job.job_id.slice(0, 8)}...` });
      navigate(`/jobs/${job.job_id}`);
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  }, [merchantId, category, startUpload, createJob, notify, navigate]);

  const handleFiles = useCallback((files: FileList | File[]) => {
    const arr = Array.from(files);
    for (const file of arr) {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        notify({ type: "error", message: `${file.name} 不是 PDF 文件` });
        continue;
      }
      if (file.size > MAX_SIZE) {
        notify({ type: "error", message: `${file.name} 超过 1GB 限制` });
        continue;
      }
      const uploadId = addFile(file);
      doUploadAndCreate(uploadId);
    }
  }, [addFile, notify, doUploadAndCreate]);

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
        <div style={{ position: "relative" }}>
          <input value={merchantId}
                 onChange={(e) => setMerchantId(e.target.value)}
                 onFocus={() => merchantList.length > 0 && setShowDropdown(true)}
                 onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
                 placeholder="例: merchant_001" className="input" />
          {showDropdown && merchantList.length > 0 && (
            <div style={{
              position: "absolute", top: "100%", left: 0, right: 0, zIndex: 10,
              background: "#fff", border: "1px solid #d9d9d9", borderRadius: 6,
              boxShadow: "0 4px 12px rgba(0,0,0,0.1)", maxHeight: 200, overflowY: "auto",
            }}>
              {merchantList
                .filter((m) => !merchantId || m.toLowerCase().includes(merchantId.toLowerCase()))
                .map((m) => (
                  <div key={m}
                       onMouseDown={() => { setMerchantId(m); setShowDropdown(false); }}
                       style={{
                         padding: "8px 12px", cursor: "pointer", fontSize: 14,
                         background: m === merchantId ? "#e6f7ff" : "#fff",
                       }}
                       onMouseEnter={(e) => { (e.target as HTMLElement).style.background = "#f5f5f5"; }}
                       onMouseLeave={(e) => { (e.target as HTMLElement).style.background = m === merchantId ? "#e6f7ff" : "#fff"; }}
                  >
                    {m}
                  </div>
                ))}
            </div>
          )}
        </div>
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
          <p className="dropzone-hint">支持批量上传，单文件最大 1GB</p>
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
                <span className="upload-status">{u.status === "uploading" ? `${u.progress.percentage}%` : u.status}</span>
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
