/**
 * Job 表格行
 */
import { JobStatusTag } from "./JobStatusTag";
import type { Job } from "../../types/models";

interface JobRowProps {
  job: Job;
  selected: boolean;
  onSelect: (id: string, checked: boolean) => void;
  onClick: (id: string) => void;
}

export function JobRow({ job, selected, onSelect, onClick }: JobRowProps) {
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
        {job.route ?? "—"}
      </td>
      <td style={{ padding: "10px 8px" }}>
        <JobStatusTag
          internalStatus={job.status}
          userStatus={job.user_status}
          actionHint={job.action_hint ?? undefined}
        />
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
