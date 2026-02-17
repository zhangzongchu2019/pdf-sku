import { useEffect, useState } from "react";
import { configApi } from "../api/config";
import { useNotificationStore } from "../stores/notificationStore";
import StatusBadge from "../components/common/StatusBadge";
import { formatPercent, formatDate } from "../utils/format";
import type { ThresholdProfile, CalibrationRecord } from "../types/models";

export default function ConfigPage() {
  const notify = useNotificationStore((s) => s.add);
  const [profile, setProfile] = useState<ThresholdProfile | null>(null);
  const [calibrations, setCalibrations] = useState<CalibrationRecord[]>([]);
  const [proposed, setProposed] = useState<Record<string, number>>({});
  const [preview, setPreview] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [reason, setReason] = useState("");

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [p, c] = await Promise.all([
        configApi.getActiveProfile(),
        configApi.getCalibrations(),
      ]);
      setProfile(p);
      setCalibrations(c.items);
      setProposed({ ...p.thresholds });
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handlePreview = async () => {
    if (!profile) return;
    setLoading(true);
    try {
      const result = await configApi.impactPreview(
        profile.profile_id, profile.thresholds, proposed
      );
      setPreview(result);
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
    setLoading(false);
  };

  const handleSave = async () => {
    if (!profile || !reason) {
      notify({ type: "error", message: "请填写变更原因" });
      return;
    }
    try {
      await configApi.updateThresholds(profile.profile_id, proposed, reason);
      notify({ type: "success", message: "阈值已更新" });
      setPreview(null);
      setReason("");
      loadData();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handleApprove = async (id: string) => {
    try {
      await configApi.approveCalibration(id);
      notify({ type: "success", message: "已批准" });
      loadData();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  const handleReject = async (id: string) => {
    const r = prompt("驳回原因:");
    if (!r) return;
    try {
      await configApi.rejectCalibration(id, r);
      notify({ type: "info", message: "已驳回" });
      loadData();
    } catch (e: any) {
      notify({ type: "error", message: e.message });
    }
  };

  return (
    <div className="page config-page">
      <h2>系统配置</h2>

      {profile && (
        <div className="card">
          <h3>阈值配置 (v{profile.version})</h3>
          <div className="threshold-grid">
            {Object.entries(profile.thresholds).map(([key, value]) => (
              <div key={key} className="threshold-item">
                <label>{key} 阈值</label>
                <div className="threshold-control">
                  <input
                    type="range" min="0" max="1" step="0.01"
                    value={proposed[key] ?? value}
                    onChange={(e) => setProposed({ ...proposed, [key]: parseFloat(e.target.value) })}
                  />
                  <span className="threshold-value">
                    {formatPercent(proposed[key] ?? value)}
                    {proposed[key] !== undefined && proposed[key] !== value && (
                      <span className="threshold-delta">
                        (原: {formatPercent(value)})
                      </span>
                    )}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="config-actions">
            <button className="btn btn-outline" onClick={handlePreview} disabled={loading}>
              {loading ? "计算中..." : "预估影响"}
            </button>
            {preview && (
              <div className="impact-preview">
                <h4>影响预估 (基于 {preview.sample_count} 样本)</h4>
                <div className="preview-grid">
                  <div>自动率: {formatPercent(preview.current_auto_rate)} → {formatPercent(preview.projected_auto_rate)}
                    <span className={preview.delta_auto >= 0 ? "positive" : "negative"}>
                      ({preview.delta_auto >= 0 ? "+" : ""}{formatPercent(preview.delta_auto)})
                    </span>
                  </div>
                  <div>人工率: {formatPercent(preview.current_human_rate)} → {formatPercent(preview.projected_human_rate)}
                    <span className={preview.delta_human <= 0 ? "positive" : "negative"}>
                      ({preview.delta_human >= 0 ? "+" : ""}{formatPercent(preview.delta_human)})
                    </span>
                  </div>
                </div>
              </div>
            )}
            <div className="form-row">
              <input className="input" placeholder="变更原因 *"
                     value={reason} onChange={(e) => setReason(e.target.value)} />
              <button className="btn btn-primary" onClick={handleSave}>保存阈值</button>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <h3>校准建议 ({calibrations.length})</h3>
        {calibrations.length === 0 ? (
          <p className="text-muted">暂无待审批的校准建议</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr><th>ID</th><th>状态</th><th>样本数</th><th>建议</th><th>创建</th><th>操作</th></tr>
            </thead>
            <tbody>
              {calibrations.map((c) => (
                <tr key={c.calibration_id}>
                  <td className="td-mono">{c.calibration_id.slice(0, 8)}...</td>
                  <td><StatusBadge status={c.status} /></td>
                  <td>{c.sample_count}</td>
                  <td className="td-ellipsis">{JSON.stringify(c.suggested_adjustments).slice(0, 50)}</td>
                  <td>{formatDate(c.created_at)}</td>
                  <td>
                    {c.status === "PENDING" && (
                      <>
                        <button className="btn btn-sm btn-success" onClick={() => handleApprove(c.calibration_id)}>批准</button>
                        <button className="btn btn-sm btn-danger" onClick={() => handleReject(c.calibration_id)}>驳回</button>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
