/**
 * 标注员列表页 /annotators
 */
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { opsApi } from "../api/ops";
import { AnnotatorTable, type AnnotatorRow } from "../components/annotator/AnnotatorTable";

export default function AnnotatorListPage() {
  const navigate = useNavigate();
  const [annotators, setAnnotators] = useState<AnnotatorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [showReassign, setShowReassign] = useState(false);
  const [reassignTaskIds, setReassignTaskIds] = useState("");
  const [reassignTarget, setReassignTarget] = useState("");
  const [reassigning, setReassigning] = useState(false);
  const [reassignResult, setReassignResult] = useState<string | null>(null);

  const fetchAnnotators = useCallback(async () => {
    try {
      setLoading(true);
      const res = await opsApi.listAnnotators();
      setAnnotators(
        res.data.map((a) => ({
          annotator_id: a.annotator_id,
          name: a.name,
          current_task: null,
          today_completed: a.daily_completed,
          avg_time_ms: a.avg_time_per_task,
          accuracy: a.accuracy,
          status: a.active_tasks > 0 ? "busy" as const : "online" as const,
        })),
      );
    } catch {
      // handle
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAnnotators(); }, [fetchAnnotators]);

  const handleReassign = async () => {
    const taskIds = reassignTaskIds
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (taskIds.length === 0 || !reassignTarget) return;
    try {
      setReassigning(true);
      setReassignResult(null);
      await opsApi.batchReassign(taskIds, reassignTarget);
      setReassignResult(`成功重分配 ${taskIds.length} 个任务`);
      setReassignTaskIds("");
      // 刷新标注员列表
      fetchAnnotators();
    } catch (e: unknown) {
      setReassignResult(`重分配失败: ${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setReassigning(false);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: "0 auto" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <h2 style={{ margin: 0, fontSize: 18, color: "#E2E8F4" }}>
          标注员管理
        </h2>
        <button
          onClick={() => { setShowReassign(true); setReassignResult(null); }}
          style={{
            padding: "6px 14px",
            backgroundColor: "#F59E0B22",
            border: "1px solid #F59E0B44",
            borderRadius: 6,
            color: "#F59E0B",
            cursor: "pointer",
            fontSize: 12,
          }}
        >
          批量重分配
        </button>
      </div>

      {loading ? (
        <div style={{ color: "#64748B" }}>加载中…</div>
      ) : (
        <AnnotatorTable
          annotators={annotators}
          onDetail={(id) => navigate(`/annotators/${id}`)}
          onAssign={(id) => navigate(`/annotators/${id}`)}
        />
      )}

      {/* 批量重分配弹窗 */}
      {showReassign && (
        <div className="modal-overlay" onClick={() => setShowReassign(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
            <div className="modal-header">
              <h3 style={{ margin: 0, fontSize: 15 }}>批量重分配任务</h3>
              <button
                onClick={() => setShowReassign(false)}
                style={{ background: "none", border: "none", color: "#94A3B8", cursor: "pointer", fontSize: 18 }}
              >×</button>
            </div>
            <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 12 }}>
              <label style={{ fontSize: 12, color: "#94A3B8" }}>
                任务 ID（每行一个，或用逗号分隔）
              </label>
              <textarea
                value={reassignTaskIds}
                onChange={(e) => setReassignTaskIds(e.target.value)}
                rows={4}
                placeholder="task-id-1&#10;task-id-2"
                style={{
                  width: "100%",
                  padding: 8,
                  backgroundColor: "#0F1729",
                  border: "1px solid #2D3548",
                  borderRadius: 6,
                  color: "#E2E8F4",
                  fontSize: 12,
                  fontFamily: "monospace",
                  resize: "vertical",
                }}
              />
              <label style={{ fontSize: 12, color: "#94A3B8" }}>
                目标标注员
              </label>
              <select
                value={reassignTarget}
                onChange={(e) => setReassignTarget(e.target.value)}
                style={{
                  width: "100%",
                  padding: 8,
                  backgroundColor: "#0F1729",
                  border: "1px solid #2D3548",
                  borderRadius: 6,
                  color: "#E2E8F4",
                  fontSize: 12,
                }}
              >
                <option value="">-- 选择标注员 --</option>
                {annotators.map((a) => (
                  <option key={a.annotator_id} value={a.annotator_id}>
                    {a.name} ({a.annotator_id.slice(0, 8)})
                  </option>
                ))}
              </select>

              {reassignResult && (
                <div style={{
                  padding: 8,
                  borderRadius: 6,
                  fontSize: 12,
                  backgroundColor: reassignResult.startsWith("成功") ? "#10B98118" : "#EF444418",
                  color: reassignResult.startsWith("成功") ? "#10B981" : "#EF4444",
                }}>
                  {reassignResult}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 4 }}>
                <button
                  onClick={() => setShowReassign(false)}
                  style={{
                    padding: "6px 14px",
                    backgroundColor: "transparent",
                    border: "1px solid #2D3548",
                    borderRadius: 6,
                    color: "#94A3B8",
                    cursor: "pointer",
                    fontSize: 12,
                  }}
                >
                  取消
                </button>
                <button
                  onClick={handleReassign}
                  disabled={reassigning || !reassignTarget || !reassignTaskIds.trim()}
                  style={{
                    padding: "6px 14px",
                    backgroundColor: reassigning ? "#F59E0B44" : "#F59E0B22",
                    border: "1px solid #F59E0B44",
                    borderRadius: 6,
                    color: "#F59E0B",
                    cursor: reassigning ? "not-allowed" : "pointer",
                    fontSize: 12,
                    opacity: (!reassignTarget || !reassignTaskIds.trim()) ? 0.5 : 1,
                  }}
                >
                  {reassigning ? "重分配中…" : "确认重分配"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
