import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAnnotationStore } from "../stores/annotationStore";
import { useJobStore } from "../stores/jobStore";
import { useNotificationStore } from "../stores/notificationStore";
import { useSettingsStore } from "../stores/settingsStore";
import StatusBadge from "../components/common/StatusBadge";
import CanvasEngine from "../components/canvas/CanvasEngine";
import GroupPanel from "../components/annotation/GroupPanel";
import ToolBar from "../components/annotation/ToolBar";
import { SLAStatusBar } from "../components/annotation/SLAStatusBar";
import { SubmitConfirmModal } from "../components/annotation/SubmitConfirmModal";
import { LockStatusIndicator } from "../components/annotation/LockStatusIndicator";
import Loading from "../components/common/Loading";

export default function AnnotationPage() {
  useParams<{ taskId: string }>();
  const navigate = useNavigate();
  const notify = useNotificationStore((s) => s.addNotification);
  const {
    currentTask, skus, annotations,
    setSkus, addAnnotation, updateAnnotation, removeAnnotation,
    selectSku, selectedSkuId,
    submitTask, skipTask, reset,
  } = useAnnotationStore();
  const { fetchSkus } = useJobStore();

  const [pageImageUrl, setPageImageUrl] = useState<string | null>(null);
  const [showSubmitConfirm, setShowSubmitConfirm] = useState(false);
  const skipSubmitConfirm = useSettingsStore((s) => s.skipSubmitConfirm);

  // Load task data
  useEffect(() => {
    if (!currentTask) {
      navigate("/tasks");
      return;
    }
    // Load page SKUs and image
    fetchSkus(currentTask.job_id, currentTask.page_number).then(() => {
      setSkus(useJobStore.getState().skus);
    });
    // Page screenshot URL
    setPageImageUrl(`/api/v1/jobs/${currentTask.job_id}/pages/${currentTask.page_number}/screenshot`);

    return () => reset();
  }, [currentTask?.task_id]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.key === "Enter") handleSubmit();
      if (e.key === "Escape") handleSkip();
      if (e.ctrlKey && e.key === "z" && annotations.length > 0) {
        removeAnnotation(annotations.length - 1);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [annotations]);

  const handleSkuEdit = useCallback((skuId: string, field: string, value: string) => {
    const idx = annotations.findIndex((a) => a.payload?.sku_id === skuId && a.payload?.field === field);
    const ann = {
      type: "SKU_ATTRIBUTE_CORRECTION",
      annotator: currentTask?.assigned_to || "",
      payload: { sku_id: skuId, field, value, action: "edit" },
    };
    if (idx >= 0) {
      updateAnnotation(idx, ann);
    } else {
      addAnnotation(ann);
    }
  }, [annotations, currentTask, addAnnotation, updateAnnotation]);

  const handleSkuValidityToggle = useCallback((skuId: string, newValidity: string) => {
    addAnnotation({
      type: "SKU_VALIDITY_CHANGE",
      annotator: currentTask?.assigned_to || "",
      payload: { sku_id: skuId, validity: newValidity },
    });
  }, [currentTask, addAnnotation]);

  const handleAddSku = useCallback(() => {
    addAnnotation({
      type: "SKU_ADD",
      annotator: currentTask?.assigned_to || "",
      payload: { action: "add", attributes: {} },
    });
  }, [currentTask, addAnnotation]);

  const handleSubmit = async () => {
    if (!skipSubmitConfirm) {
      setShowSubmitConfirm(true);
      return;
    }
    await doSubmit();
  };

  const doSubmit = async () => {
    try {
      await submitTask();
      notify({ type: "success", message: "标注提交成功" });
      navigate("/tasks");
    } catch (e: unknown) {
      const err = e as Error;
      notify({ type: "error", message: err.message });
    }
  };

  const handleSkip = async () => {
    if (!confirm("确定跳过此任务？")) return;
    try {
      await skipTask("标注员手动跳过");
      notify({ type: "info", message: "已跳过" });
      navigate("/tasks");
    } catch (e: unknown) {
      const err = e as Error;
      notify({ type: "error", message: err.message });
    }
  };

  if (!currentTask) return <Loading text="加载任务..." />;

  return (
    <div className="page annotation-page">
      {/* SLA status bar */}
      {currentTask.timeout_at && (
        <SLAStatusBar
          deadline={currentTask.timeout_at}
          slaLevel="NORMAL"
          taskId={currentTask.task_id}
          reworkCount={currentTask.rework_count}
        />
      )}

      {/* Lock indicator */}
      <LockStatusIndicator
        lockedBy={currentTask.locked_by ?? null}
        lockedAt={currentTask.timeout_at ?? null}
        timeoutAt={currentTask.timeout_at ?? null}
        currentUserId=""
      />

      <div className="annotation-header">
        <div className="task-info">
          <h2>标注: {currentTask.task_type}</h2>
          <span>Job: {currentTask.job_id.slice(0, 8)}... | 页码: {currentTask.page_number}</span>
          <StatusBadge status={currentTask.status} />
          {currentTask.rework_count > 0 && (
            <span style={{ marginLeft: 8, fontSize: 11, padding: "1px 6px", backgroundColor: "#F59E0B18", border: "1px solid #F59E0B33", borderRadius: 3, color: "#F59E0B" }}>
              返工 ×{currentTask.rework_count}
            </span>
          )}
        </div>
        <ToolBar
          onSubmit={handleSubmit}
          onSkip={handleSkip}
          onAddSku={handleAddSku}
          annotationCount={annotations.length}
        />
      </div>

      <div className="annotation-workspace">
        <div className="canvas-panel">
          <CanvasEngine
            imageUrl={pageImageUrl}
            skus={skus}
            selectedSkuId={selectedSkuId}
            onSelectSku={selectSku}
            annotations={annotations}
          />
        </div>

        <div className="sidebar-panel">
          <GroupPanel
            skus={skus}
            annotations={annotations}
            selectedSkuId={selectedSkuId}
            onSelectSku={selectSku}
            onEditSku={handleSkuEdit}
            onToggleValidity={handleSkuValidityToggle}
            onRemoveAnnotation={removeAnnotation}
          />
        </div>
      </div>

      {/* Submit confirmation modal */}
      {showSubmitConfirm && (
        <SubmitConfirmModal
          visible={true}
          ungroupedCount={0}
          groupCount={0}
          warningMessages={[]}
          onConfirm={() => { setShowSubmitConfirm(false); doSubmit(); }}
          onCancel={() => setShowSubmitConfirm(false)}
        />
      )}
    </div>
  );
}
