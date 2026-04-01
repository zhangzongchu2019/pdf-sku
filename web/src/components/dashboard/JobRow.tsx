/**
 * Job 表格行
 */
import { useState } from "react";
import { JobStatusTag } from "./JobStatusTag";
import { useJobStore } from "../../stores/jobStore";
import { statusLabel } from "../../utils/format";
import type { Job } from "../../types/models";

interface JobRowProps {
  job: Job;
  selected: boolean;
  onSelect: (id: string, checked: boolean) => void;
  onClick: (id: string) => void;
}

/** 可重试的 Job 状态（明确失败/降级的） */
const RETRYABLE_STATUSES = new Set([
  "DEGRADED_HUMAN", "EVAL_FAILED", "ORPHANED",
  "PARTIAL_FAILED", "CANCELLED", "REJECTED",
]);

/** 根据状态和降级原因返回失败提示文案 */
function failureHint(job: Job): string | null {
  if (!RETRYABLE_STATUSES.has(job.status)) return null;
  if (job.status === "DEGRADED_HUMAN" && job.degrade_reason?.startsWith("eval_failed"))
    return "AI 模型调用超时";
  if (job.status === "DEGRADED_HUMAN") return "已降级为人工处理";
  if (job.status === "EVAL_FAILED") return "评估失败";
  if (job.status === "PARTIAL_FAILED") return "部分页面处理失败";
  if (job.status === "ORPHANED") return "处理中断";
  if (job.status === "CANCELLED") return "已取消";
  if (job.status === "REJECTED") return "文件被拒绝";
  return null;
}

export function JobRow({ job, selected, onSelect, onClick }: JobRowProps) {
  const retryJob = useJobStore((s) => s.retryJob);
  const fetchJobs = useJobStore((s) => s.fetchJobs);
  const [retrying, setRetrying] = useState(false);
  const completedCount = job.ai_pages.length + job.human_pages.length;
  const progress =
    job.total_pages > 0
      ? Math.round((completedCount / job.total_pages) * 100)
      : 0;

  return (
    <tr
      style={{
        cursor: "pointer",
        backgroundColor: selected ? "#22D3EE08" : "transparent",
        borderBottom: "1px solid #2D3548",
      }}
      onClick={() => onClick(job.job_id)}
    >
      <td style={{ padding: "10px 8px" }}>
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => {
            e.stopPropagation();
            onSelect(job.job_id, e.target.checked);
          }}
          style={{ accentColor: "#22D3EE" }}
        />
      </td>
      <td style={{ padding: "10px 8px", color: "#E2E8F4", fontSize: 13 }}>
        <div
          style={{
            maxWidth: 200,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
          title={job.source_file}
        >
          {job.source_file}
        </div>
      </td>
      <td style={{ padding: "10px 8px", color: "#94A3B8", fontSize: 12 }}>
        {job.merchant_id ?? "—"}
      </td>
      <td style={{ padding: "10px 8px", color: "#94A3B8", fontSize: 12 }}>
        {job.total_pages}
      </td>
      <td style={{ padding: "10px 8px", color: "#94A3B8", fontSize: 12 }}>
        {statusLabel(job.route) ?? "—"}
      </td>
      <td style={{ padding: "10px 8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          <JobStatusTag
            internalStatus={job.status}
            userStatus={job.user_status}
            actionHint={job.action_hint ?? undefined}
          />
          {failureHint(job) && !retrying && (
            <>
              <span style={{ fontSize: 11, color: "#EF4444" }}>
                {failureHint(job)}
              </span>
              <button
                onClick={async (e) => {
                  e.stopPropagation();
                  setRetrying(true);
                  try {
                    await retryJob(job.job_id);
                    await fetchJobs();
                  } finally {
                    setRetrying(false);
                  }
                }}
                style={{
                  padding: "2px 8px",
                  backgroundColor: "#3B82F620",
                  border: "1px solid #3B82F644",
                  borderRadius: 4,
                  color: "#3B82F6",
                  cursor: "pointer",
                  fontSize: 11,
                  fontWeight: 500,
                  whiteSpace: "nowrap",
                }}
              >
                重新分析
              </button>
            </>
          )}
          {retrying && (
            <span style={{ fontSize: 11, color: "#3B82F6" }}>
              已提交重新分析，处理中...
            </span>
          )}
        </div>
      </td>
      <td style={{ padding: "10px 8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <div
            style={{
              flex: 1,
              height: 4,
              backgroundColor: "#2D3548",
              borderRadius: 2,
              overflow: "hidden",
            }}
          >
            <div
              style={{
                width: `${progress}%`,
                height: "100%",
                backgroundColor: progress === 100 ? "#22C55E" : "#22D3EE",
                transition: "width 0.3s ease",
              }}
            />
          </div>
          <span style={{ fontSize: 11, color: "#64748B", minWidth: 35, textAlign: "right" }}>
            {progress}%
          </span>
        </div>
      </td>
      <td style={{ padding: "10px 8px", color: "#94A3B8", fontSize: 12 }}>
        {job.human_pages.length}
      </td>
      <td style={{ padding: "10px 8px" }}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onClick(job.job_id);
          }}
          style={{
            padding: "3px 10px",
            backgroundColor: "transparent",
            border: "1px solid #2D3548",
            borderRadius: 4,
            color: "#94A3B8",
            cursor: "pointer",
            fontSize: 11,
          }}
        >
          详情
        </button>
      </td>
    </tr>
  );
}

export default JobRow;
